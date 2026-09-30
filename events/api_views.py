import hashlib
import json

from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.http import parse_etags, quote_etag
from datetime import datetime

from events.exceptions import (
    EntryClosedError, InvalidResultsError, ParticipantNotFoundError, ParticipantTooYoungError,
    RegistrationClosedError, ResultsUpdateNotAllowedError, SetFullError, WithoutRegistrationDisabledError,
)
from events.models import Event, Participant, Route, Wallet, PromoCode
from events import services
from events.serializers import (
    EntryRegistrationSerializer, EventSerializer, ParticipantSerializer, RouteSerializer,
    WalletSerializer, PromoCodeSerializer
)

# ошибки ввода результатов участником: исключение -> (HTTP-статус, код для клиента)
ENTRY_ERRORS = {
    ParticipantNotFoundError: (status.HTTP_404_NOT_FOUND, 'pin_not_found'),
    EntryClosedError: (status.HTTP_403_FORBIDDEN, 'entry_closed'),
    ResultsUpdateNotAllowedError: (status.HTTP_403_FORBIDDEN, 'update_not_allowed'),
    RegistrationClosedError: (status.HTTP_403_FORBIDDEN, 'registration_closed'),
    WithoutRegistrationDisabledError: (status.HTTP_403_FORBIDDEN, 'without_registration_disabled'),
    SetFullError: (status.HTTP_400_BAD_REQUEST, 'set_full'),
    ParticipantTooYoungError: (status.HTTP_400_BAD_REQUEST, 'too_young'),
    InvalidResultsError: (status.HTTP_400_BAD_REQUEST, 'invalid_results'),
}


def _entry_error_response(exc: Exception) -> Response:
    http_status, code = ENTRY_ERRORS[type(exc)]
    body = {'error': str(exc), 'code': code}
    if isinstance(exc, InvalidResultsError):
        body['routes'] = exc.routes
    return Response(body, status=http_status)


def _ensure_event_editor(request, event: Event) -> None:
    """Массовый ввод и правка результатов: только организатор события и суперпользователь"""
    user = request.user
    if not (user and user.is_authenticated and (user.is_superuser or event.owner_id == user.id)):
        raise PermissionDenied('Доступно только организатору события.')


def _entry_payload(event: Event, participant: Participant, with_standing: bool = False) -> dict:
    payload = {
        'participant': services.get_participant_public(event=event, participant=participant),
        'results': services.get_participant_results(event=event, participant=participant),
    }
    if with_standing:
        payload['standing'] = services.get_participant_standing(event=event, participant=participant)
    return payload

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # superuser check
        if request.user and request.user.is_superuser:
            return True
        # object owner check
        return getattr(obj, 'owner', None) == request.user


class IsEventOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow event owners to edit event-related items.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_superuser:
            return True
        return obj.event.owner == request.user


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated:
            if user.is_superuser:
                return Event.objects.all().order_by('-date')
            return Event.objects.filter(Q(is_published=True) | Q(owner=user)).order_by('-date')
        return Event.objects.filter(is_published=True).order_by('-date')

    def perform_create(self, serializer):
        event = services.create_event(
            owner=self.request.user,
            title=serializer.validated_data.get('title'),
            date=serializer.validated_data.get('date', datetime.today().date())
        )
        # Update other validated fields
        for field, value in serializer.validated_data.items():
            if field not in ['owner', 'title', 'date']:
                setattr(event, field, value)
        event.save()

    @action(detail=True, methods=['get'], url_path='entry/config', permission_classes=[permissions.AllowAny])
    def entry_config(self, request, pk=None):
        return Response(services.get_entry_config(event=self.get_object()))

    @action(detail=True, methods=['post'], url_path='entry/identify', permission_classes=[permissions.AllowAny])
    def entry_identify(self, request, pk=None):
        event = self.get_object()
        try:
            participant = services.identify_participant(event=event, pin=request.data.get('pin'))
        except tuple(ENTRY_ERRORS) as e:
            return _entry_error_response(e)
        return Response(_entry_payload(event=event, participant=participant))

    @action(detail=True, methods=['post'], url_path='entry/submit', permission_classes=[permissions.AllowAny])
    def entry_submit(self, request, pk=None):
        event = self.get_object()
        try:
            participant = services.submit_results_by_pin(event=event, pin=request.data.get('pin'),
                                                         raw_results=request.data.get('results'))
        except tuple(ENTRY_ERRORS) as e:
            return _entry_error_response(e)
        return Response(_entry_payload(event=event, participant=participant, with_standing=True))

    @action(detail=True, methods=['post'], url_path='entry/submit-without-registration',
            permission_classes=[permissions.AllowAny])
    def entry_submit_without_registration(self, request, pk=None):
        event = self.get_object()
        serializer = EntryRegistrationSerializer(data=request.data, event=event)
        if not serializer.is_valid():
            return Response({'error': 'Проверьте заполнение анкеты.', 'code': 'invalid_fields',
                             'fields': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            participant = services.submit_results_without_registration(
                event=event, cd=serializer.validated_data, raw_results=request.data.get('results'))
        except tuple(ENTRY_ERRORS) as e:
            return _entry_error_response(e)
        return Response(_entry_payload(event=event, participant=participant, with_standing=True))

    @action(detail=True, methods=['get'], url_path='results', permission_classes=[permissions.AllowAny])
    def results(self, request, pk=None):
        """Результаты события по таблице на каждый пол и группу. Экран опрашивает его раз в 30 секунд,
        поэтому ответ отдаётся с ETag и на неизменившиеся данные отвечает 304 без тела."""
        event = self.get_object()
        if not event.is_results_allowed:
            return Response({'error': 'Просмотр результатов закрыт.', 'code': 'results_closed'},
                            status=status.HTTP_403_FORBIDDEN)
        user = request.user
        can_edit = bool(user and user.is_authenticated and (user.is_superuser or event.owner_id == user.id))
        payload = services.get_results_payload(event=event, can_edit=can_edit)
        etag = quote_etag(hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
        if etag in parse_etags(request.META.get('HTTP_IF_NONE_MATCH', '')):
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
        else:
            response = Response(payload)
        response['ETag'] = etag
        response['Cache-Control'] = 'private, no-cache'
        return response

    @action(detail=True, methods=['get'], url_path='matrix', permission_classes=[permissions.IsAuthenticated])
    def matrix(self, request, pk=None):
        """Участники события с PIN и результатами для массового ввода организатором"""
        event = self.get_object()
        _ensure_event_editor(request, event)
        return Response(services.get_matrix_payload(event=event))

    @action(detail=True, methods=['post'], url_path='matrix/save', permission_classes=[permissions.IsAuthenticated])
    def matrix_save(self, request, pk=None):
        """Сохраняет изменённые ячейки матрицы и отдаёт свежие данные с пересчитанными местами"""
        event = self.get_object()
        _ensure_event_editor(request, event)
        try:
            saved = services.save_matrix_changes(event=event, changes=request.data.get('changes'))
        except ParticipantNotFoundError as e:
            return Response({'error': str(e), 'code': 'participant_not_found'}, status=status.HTTP_404_NOT_FOUND)
        except InvalidResultsError as e:
            return Response({'error': str(e), 'code': 'invalid_results', 'routes': e.routes,
                             'participant': e.participant_id}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**services.get_matrix_payload(event=event), 'saved': saved})


class ParticipantViewSet(viewsets.ModelViewSet):
    serializer_class = ParticipantSerializer

    def get_permissions(self):
        if self.action == 'create' or self.action == 'enter_results':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsEventOwnerOrReadOnly()]

    def get_queryset(self):
        user = self.request.user
        event_id = self.request.query_params.get('event')
        
        # If filtering by event
        if event_id:
            event = get_object_or_404(Event, id=event_id)
            # If event is published or user has rights
            if event.is_published or (user and user.is_authenticated and (event.owner == user or user.is_superuser)):
                return event.participant.all().order_by('last_name')
            return Participant.objects.none()

        # If not filtering, check user
        if user and user.is_authenticated:
            if user.is_superuser:
                return Participant.objects.all().order_by('last_name')
            return Participant.objects.filter(Q(event__owner=user) | Q(event__is_published=True)).order_by('last_name')
        
        # Anonymous can only see participants of published events
        return Participant.objects.filter(event__is_published=True).order_by('last_name')

    def create(self, request, *args, **kwargs):
        event_id = request.data.get('event')
        if not event_id:
            return Response({"error": "Event ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        event = get_object_or_404(Event, id=event_id)

        if not services.is_registration_open(event):
            return Response({"error": "Registration is closed for this event"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cd = serializer.validated_data
        cd_copy = dict(cd)

        # Map indices to names for the service
        groups = services.get_group_list(event)
        sets = services.get_set_list(event)
        if len(groups) <= 1 or 'group_index' not in cd_copy:
            cd_copy.pop('group_index', None)
        else:
            try:
                cd_copy['group_index'] = groups[cd_copy['group_index']]
            except (IndexError, TypeError):
                cd_copy.pop('group_index', None)

        if len(sets) == 0 or 'set_index' not in cd_copy:
            cd_copy.pop('set_index', None)
        else:
            try:
                cd_copy['set_index'] = sets[cd_copy['set_index']]
            except (IndexError, TypeError):
                cd_copy.pop('set_index', None)

        try:
            participant = services.register_participant(event, cd_copy)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not participant:
            return Response({"error": "Could not register participant"}, status=status.HTTP_400_BAD_REQUEST)

        # Return registered participant with pin
        headers = self.get_success_headers(serializer.data)
        return Response({
            "id": participant.id,
            "first_name": participant.first_name,
            "last_name": participant.last_name,
            "pin": participant.pin,
            "gender": participant.gender,
            "birth_year": participant.birth_year,
            "city": participant.city,
            "team": participant.team,
            "grade": participant.grade,
            "group_index": participant.group_index,
            "set_index": participant.set_index
        }, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        participant = serializer.instance
        event = participant.event
        
        cd_copy = dict(serializer.validated_data)
        groups = services.get_group_list(event)
        sets = services.get_set_list(event)
        if len(groups) <= 1 or 'group_index' not in cd_copy:
            cd_copy.pop('group_index', None)
        else:
            try:
                cd_copy['group_index'] = groups[cd_copy['group_index']]
            except (IndexError, TypeError):
                cd_copy.pop('group_index', None)

        if len(sets) == 0 or 'set_index' not in cd_copy:
            cd_copy.pop('set_index', None)
        else:
            try:
                cd_copy['set_index'] = sets[cd_copy['set_index']]
            except (IndexError, TypeError):
                cd_copy.pop('set_index', None)

        services.update_participant(event, participant, cd_copy)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def enter_results(self, request, pk=None):
        participant = self.get_object()
        event = participant.event

        pin = request.data.get('pin')
        try:
            if pin is None or int(pin) != participant.pin:
                return Response({"error": "Invalid PIN code"}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Invalid PIN code"}, status=status.HTTP_400_BAD_REQUEST)

        accents = request.data.get('accents')
        if accents is None:
            return Response({"error": "Accents data is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            services.enter_results(event=event, participant=participant, accents=accents)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "results entered successfully"}, status=status.HTTP_200_OK)


class RouteViewSet(viewsets.ModelViewSet):
    serializer_class = RouteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsEventOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        event_id = self.request.query_params.get('event')

        if event_id:
            event = get_object_or_404(Event, id=event_id)
            if event.is_published or (user and user.is_authenticated and (event.owner == user or user.is_superuser)):
                return event.route.all().order_by('number')
            return Route.objects.none()

        if user and user.is_authenticated:
            if user.is_superuser:
                return Route.objects.all().order_by('event', 'number')
            return Route.objects.filter(Q(event__is_published=True) | Q(event__owner=user)).order_by('event', 'number')

        return Route.objects.filter(event__is_published=True).order_by('event', 'number')

    def perform_update(self, serializer):
        route = serializer.save()
        services.update_results(route.event)

    def perform_create(self, serializer):
        event = serializer.validated_data.get('event')
        if not event:
            raise serializers.ValidationError({"event": "Event is required."})
        user = self.request.user
        if not user.is_superuser and event.owner != user:
            raise permissions.exceptions.PermissionDenied("You are not the owner of this event.")
        route = serializer.save()
        services.update_results(route.event)


class WalletViewSet(viewsets.ModelViewSet):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Wallet.objects.all()
        return Wallet.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class PromoCodeViewSet(viewsets.ModelViewSet):
    serializer_class = PromoCodeSerializer
    permission_classes = [permissions.IsAuthenticated, IsEventOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return PromoCode.objects.all()
        return PromoCode.objects.filter(event__owner=user)


class StatApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):
        stats = services.get_platform_stats()
        return Response(stats, status=status.HTTP_200_OK)

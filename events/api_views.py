from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404
from datetime import datetime

from events.models import Event, Participant, Route, Wallet, PromoCode
from events import services
from events.serializers import (
    EventSerializer, ParticipantSerializer, RouteSerializer, 
    WalletSerializer, PromoCodeSerializer
)

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
        if pin is None or int(pin) != participant.pin:
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

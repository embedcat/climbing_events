from collections.abc import Mapping

from rest_framework import serializers
from django.contrib.auth import get_user_model
from events.models import Event, Participant, Route, Wallet, PromoCode, PayDetail

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['id', 'owner', 'title', 'wallet_id', 'notify_secret_key']
        read_only_fields = ['owner']


class EventSerializer(serializers.ModelSerializer):
    owner_details = UserSerializer(source='owner', read_only=True)
    
    def validate(self, attrs):
        date = attrs.get('date', getattr(self.instance, 'date', None))
        date_end = attrs.get('date_end', getattr(self.instance, 'date_end', None))
        if date and date_end and date_end < date:
            raise serializers.ValidationError({'date_end': 'Дата окончания не может быть раньше даты начала.'})
        return attrs

    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['owner']


class ParticipantSerializer(serializers.ModelSerializer):
    # видят только организатор события и суперадмин (docs/PRODUCT.md, «Регистрация и участники»)
    PRIVATE_FIELDS = ('email', 'phone_number', 'birth_date')

    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    team = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        # до сохранения (serializer.data в ParticipantViewSet.create) сюда приходит validated_data — dict
        event = instance.get('event') if isinstance(instance, Mapping) else instance.event
        is_owner = user is not None and user.is_authenticated and (
            user.is_superuser or (event is not None and event.owner_id == user.id))
        if not is_owner:
            for field in self.PRIVATE_FIELDS:
                data.pop(field, None)
        return data

    class Meta:
        model = Participant
        fields = '__all__'
        read_only_fields = [
            'pin', 'score', 'place', 'is_entered_result', 
            'french_accents', 'french_score', 'scores', 'counted_routes'
        ]


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = '__all__'


class PayDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayDetail
        fields = '__all__'

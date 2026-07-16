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
    
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['owner']


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = '__all__'
        read_only_fields = [
            'pin', 'score', 'place', 'is_entered_result', 
            'accents', 'french_accents', 'french_score', 'scores', 'counted_routes'
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

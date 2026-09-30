from datetime import date

from rest_framework import serializers
from django.contrib.auth import get_user_model
from phonenumber_field.serializerfields import PhoneNumberField

from events import services
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
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    team = serializers.CharField(required=False, allow_blank=True, allow_null=True)

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


class EntryRegistrationSerializer(serializers.Serializer):
    """ Анкета участника при вводе без регистрации. Набор полей зависит от настроек события """
    first_name = serializers.CharField(max_length=Participant._meta.get_field('first_name').max_length)
    last_name = serializers.CharField(max_length=Participant._meta.get_field('last_name').max_length)

    def __init__(self, *args, event: Event, **kwargs):
        super().__init__(*args, **kwargs)
        fields = services.get_registration_fields(event=event)
        required = services.get_registration_required_fields(event=event)

        if Event.FIELD_GENDER in fields:
            self.fields[Event.FIELD_GENDER] = serializers.ChoiceField(choices=Participant.GENDERS)
        if Event.FIELD_BIRTH_YEAR in fields:
            self.fields[Event.FIELD_BIRTH_YEAR] = serializers.IntegerField(
                min_value=1900, max_value=date.today().year, required=Event.FIELD_BIRTH_YEAR in required)
        for name in (Event.FIELD_CITY, Event.FIELD_TEAM):
            if name in fields:
                self.fields[name] = serializers.CharField(
                    max_length=Participant._meta.get_field(name).max_length,
                    required=name in required, allow_blank=name not in required)
        if Event.FIELD_GRADE in fields:
            self.fields[Event.FIELD_GRADE] = serializers.ChoiceField(choices=Participant.GRADES, required=False)
        if Event.FIELD_EMAIL in fields:
            self.fields[Event.FIELD_EMAIL] = serializers.EmailField(
                max_length=Participant._meta.get_field('email').max_length,
                required=Event.FIELD_EMAIL in required, allow_blank=Event.FIELD_EMAIL not in required)
        if Event.FIELD_PHONE in fields:
            self.fields[Event.FIELD_PHONE] = PhoneNumberField(
                required=Event.FIELD_PHONE in required, allow_blank=Event.FIELD_PHONE not in required)
        if event.group_num > 1:
            self.fields['group_index'] = serializers.IntegerField(
                min_value=0, max_value=len(services.get_group_list(event=event)) - 1)
        sets = services.get_set_list(event=event)
        if sets:
            self.fields['set_index'] = serializers.IntegerField(min_value=0, max_value=len(sets) - 1)

    def validate(self, attrs):
        if Event.FIELD_PHONE in attrs:
            attrs[Event.FIELD_PHONE] = str(attrs[Event.FIELD_PHONE] or '')
        return attrs

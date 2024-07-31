from rest_framework import serializers
from core.models import (
    Instrument,
    SubscribedInstruments,
    Candle,
    BreezeAccount,
    PercentageInstrument,
)


class PercentageInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PercentageInstrument
        fields = ['percentage', 'is_loading']


class AllInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = "__all__"


class SubscribedSerializer(serializers.ModelSerializer):
    percentage = PercentageInstrumentSerializer(many=True, read_only=True)

    class Meta:
        model = SubscribedInstruments
        fields = "__all__"


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = "__all__"

    def to_representation(self, instance):
        if isinstance(instance, SubscribedSerializer):
            serializer = SubscribedSerializer(instance=instance)
        else:
            serializer = AllInstrumentSerializer(instance=instance)
        return serializer.data


class CandleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candle
        fields = ["open", "high", "low", "close","volume", "date"]


class BreezeAccountSerialzer(serializers.ModelSerializer):
    class Meta:
        model = BreezeAccount
        fields = "__all__"

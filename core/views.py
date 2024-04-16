from django.shortcuts import render
import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from core.tasks import (
    load_data,
    get_master_data,
    resample_candles,
    load_instrument_candles,
)
from core.models import (
    BreezeAccount,
    Exchanges,
    Tick,
    Instrument,
    SubscribedInstruments,
    Candle,
    Percentage,
)
from core.serializers import (
    InstrumentSerializer,
    SubscribedSerializer,
    CandleSerializer,
    AllInstrumentSerializer,
    BreezeAccountSerialzer,
)
import urllib

# Create your views here.


def item_list(request):
    items = Candle.objects.all().order_by("-date")
    context = {"items": items[:50]}
    return render(request, "test.html", context)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_access_code(request):
    acc = BreezeAccount.objects.all().last()
    return Response(
        "https://api.icicidirect.com/apiuser/login?api_key="
        + urllib.parse.quote_plus(acc.api_key)
    )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def get_breeze_accounts(request):
    if request.method == "GET":
        acc = BreezeAccount.objects.all()
        data = BreezeAccountSerialzer(acc, many=True).data
        # data[0]["url"] = (
        #     "https://api.icicidirect.com/apiuser/login?api_key="
        #     + urllib.parse.quote_plus(acc[0].api_key)
        # )

        return Response({"msg": "Okay", "data": data}, status=200)
    if request.method == "POST":
        id = request.data.get("id")
        instance = BreezeAccount.objects.get(id=id)
        serializer = BreezeAccountSerialzer(data=request.data)
        if serializer.is_valid():
            serializer.update(
                instance=instance, validated_data=serializer.validated_data
            )
        return Response({"msg": "Okay", "data": serializer.validated_data}, status=200)


@api_view(["GET"])
@permission_classes([AllowAny])
def setup(request):
    get_master_data()
    timestamp = str(
        datetime.datetime.now()
    )  # unique timestamp to identify all tasks from same instance
    per = Percentage.objects.create(source=timestamp, value=0)
    for exc in Exchanges.objects.all():
        load_data.delay(exc.id, timestamp)
    return Response({"working": "fine"})


@api_view(["POST"])
@permission_classes([AllowAny])
def subscribe_instrument(request, pk):
    id = pk
    ins = Instrument.objects.filter(id=pk)
    if not ins.exists():
        return Response({"error": "doesn't exist"})

    ins = ins[0]
    data = InstrumentSerializer(ins).data
    data.pop("id")
    ex_id = data.pop("exchange")
    if SubscribedInstruments.objects.filter(**data).exists():
        return Response({"error": "already subscribed"})

    sub_ins = SubscribedInstruments(exchange_id=ex_id, **data)
    sub_ins.save()

    return Response({"msg": "success", "data": InstrumentSerializer(sub_ins).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def get_instrument_candles(request, pk):
    qs = SubscribedInstruments.objects.filter(id=pk)

    if qs.exists():
        load_instrument_candles.delay(qs[0].id)
        return Response({"msg": "success"})
    return Response({"msg": "error"})


@api_view(["DELETE", "POST"])
@permission_classes([AllowAny])
def delete_instrument(request, pk):
    qs = SubscribedInstruments.objects.filter(id=pk)

    if qs.exists():
        qs.delete()
        return Response({"msg": "success"})
    return Response({"msg": "error"})


@api_view(["GET"])
@permission_classes([AllowAny])
def get_subscribed_instruments(request):
    qs = SubscribedInstruments.objects.all()
    data = SubscribedSerializer(qs, many=True).data

    return Response({"msg": "success", "data": data})


@api_view(["GET"])
@permission_classes([AllowAny])
def get_candles(request):
    id = request.GET.get("id")
    tf = request.GET.get("tf")

    qs = SubscribedInstruments.objects.filter(id=id)
    if qs.exists():
        instrument = qs[0]
        qs_2 = Candle.objects.filter(instrument=instrument).order_by("date")
        if tf:
            timeframe = int(tf)
            qs_2 = resample_candles(qs_2, timeframe)

        data = CandleSerializer(qs_2, many=True).data
        return Response({"msg": "done", "data": data}, status=200)
    else:
        return Response({"msg": "Error"})


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_instruments(request):
    exchange = request.GET.get("exchange")
    search_term = request.GET.get("search")

    if len(search_term) < 2:
        return Response({"msg": "Add More Terms"})

    qs_1 = Exchanges.objects.filter(title=exchange).last()
    if qs_1.title == "FON":
        qs = Instrument.objects.filter(
            exchange=qs_1, exchange_code__icontains=search_term
        )[:50]
    else:
        qs = Instrument.objects.filter(
            exchange=qs_1, exchange_code__icontains=search_term
        )

    if qs.exists():
        data = AllInstrumentSerializer(qs, many=True).data

        return Response({"msg": "Ok", "data": data})

    return Response({"msg": "Error"})

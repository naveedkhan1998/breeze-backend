import datetime
from django.db.models import Q
from rest_framework import status
from django.shortcuts import render
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticated
from django.shortcuts import get_object_or_404
from functools import lru_cache
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
    PercentageInstrument,
)
from core.serializers import (
    InstrumentSerializer,
    SubscribedSerializer,
    CandleSerializer,
    AllInstrumentSerializer,
    BreezeAccountSerialzer,
    PercentageInstrumentSerializer,
)
import urllib

# Create your views here.


def item_list(request):
    items = Candle.objects.all().order_by("-date")
    context = {"items": items[:50]}
    return render(request, "test.html", context)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_access_code(request):
    acc = BreezeAccount.objects.filter(user=request.user)
    if acc.exists():
        return Response(
            "https://api.icicidirect.com/apiuser/login?api_key="
            + urllib.parse.quote_plus(acc.api_key)
        )
    return Response({"msg": "Error"}, status=400)


@api_view(["GET", "POST", "PUT"])
@permission_classes([IsAuthenticated])
def get_breeze_accounts(request):
    if request.method == "GET":
        acc = BreezeAccount.objects.filter(user=request.user)
        if acc.exists():
            data = BreezeAccountSerialzer(acc, many=True).data
            return Response({"msg": "Okay", "data": data}, status=status.HTTP_200_OK)
        return Response({"msg": "No accounts found"}, status=status.HTTP_404_NOT_FOUND)

    elif request.method == "POST":
        serializer = BreezeAccountSerialzer(data=request.data)
        #print(request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(
                {"msg": "Account created successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "PUT":
        id = request.data.get("id")
        try:
            instance = BreezeAccount.objects.get(id=id, user=request.user)
        except BreezeAccount.DoesNotExist:
            return Response(
                {"msg": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = BreezeAccountSerialzer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"msg": "Account updated successfully", "data": serializer.data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def setup(request):
    get_master_data()
    for exc in Exchanges.objects.all():
        # if exc.title == "FON":
        #    continue
        per, created = Percentage.objects.get_or_create(source=exc.title)
        if not created:
            per.value = 0
            per.save()
        load_data.delay(exc.id, exc.title)
    return Response({"working": "fine"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def subscribe_instrument(request, pk):
    id = pk
    ins = Instrument.objects.filter(id=pk)
    if not ins.exists():
        return Response({"error": "doesn't exist"})

    ins = ins[0]
    data = InstrumentSerializer(ins).data
    data.pop("id")
    # get the no of weeks to fetch historic data for
    duration = request.data.get("duration")
    ex_id = data.pop("exchange")
    if SubscribedInstruments.objects.filter(**data).exists():
        return Response({"error": "already subscribed"})

    sub_ins = SubscribedInstruments(exchange_id=ex_id, **data)
    sub_ins.save()
    load_instrument_candles.delay(sub_ins.id, request.user.id,duration=duration)

    return Response({"msg": "success", "data": InstrumentSerializer(sub_ins).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_instrument_percentage(request, pk):
    qs = PercentageInstrument.objects.filter(instrument__id=pk)

    if qs.exists():
        data = PercentageInstrumentSerializer(qs, many=True).data
        return Response({"msg": "Okay", "data": data}, status=status.HTTP_200_OK)
    return Response({"msg": "No accounts found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_instrument_candles(request, pk):
    qs = SubscribedInstruments.objects.filter(id=pk)

    if qs.exists():
        cache.clear()
        load_instrument_candles.delay(qs[0].id, request.user.id)
        return Response({"msg": "success"})
    return Response({"msg": "error"})


@api_view(["DELETE", "POST"])
@permission_classes([IsAuthenticated])
def delete_instrument(request, pk):
    qs = SubscribedInstruments.objects.filter(id=pk)

    if qs.exists():
        qs.delete()
        return Response({"msg": "success"})
    return Response({"msg": "error"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_subscribed_instruments(request):
    qs = SubscribedInstruments.objects.all()
    data = SubscribedSerializer(qs, many=True).data

    return Response({"msg": "success", "data": data})


@lru_cache(maxsize=128)
def get_cached_candles(instrument_id):
    instrument = get_object_or_404(SubscribedInstruments, id=instrument_id)
    qs = Candle.objects.filter(instrument=instrument).order_by("date")
    return CandleSerializer(qs, many=True).data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_candles(request):
    instrument_id = request.GET.get("id")
    tf = request.GET.get("tf")
    # cache.clear()
    if not instrument_id:
        return Response({"msg": "Missing instrument ID"}, status=400)

    cache_key = f"candles_{instrument_id}_{tf}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return Response({"msg": "Loaded From Cache", "data": cached_data}, status=200)

    candles = get_cached_candles(instrument_id)

    if tf:
        try:
            timeframe = int(tf)
            new_candles = resample_candles(candles, timeframe)
        except ValueError:
            return Response({"msg": "Invalid timeframe"}, status=400)
    else:
        new_candles = candles

    cache.set(cache_key, new_candles, timeout=60 * 10)
    return Response({"msg": "done", "data": new_candles}, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_instruments(request):
    exchange = request.GET.get("exchange")
    search_term = request.GET.get("search")

    if not exchange:
        return Response({"msg": "Exchange is required"}, status=400)

    if not search_term or len(search_term) < 2:
        return Response(
            {"msg": "Search term must be at least 2 characters long"}, status=400
        )

    qs_1 = Exchanges.objects.filter(title=exchange).last()
    if not qs_1:
        return Response({"msg": "Invalid Exchange"}, status=400)

    # Create filters based on the search term
    filters = Q(exchange=qs_1) & (
        Q(strike_price__icontains=search_term)
        | Q(short_name__icontains=search_term)
        | Q(company_name__icontains=search_term)
        | Q(stock_token__icontains=search_term)
        | Q(token__icontains=search_term)
        | Q(instrument__icontains=search_term)
        | Q(series__icontains=search_term)
        | Q(option_type__icontains=search_term)
        | Q(exchange_code__icontains=search_term)
    )

    qs = Instrument.objects.filter(filters)

    if qs_1.title == "FON":
        qs = qs[:50]

    if qs.exists():
        data = AllInstrumentSerializer(qs, many=True).data
        return Response({"msg": "Ok", "data": data})

    return Response({"msg": "No instruments found"}, status=404)

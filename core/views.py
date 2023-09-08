from django.shortcuts import render
import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from core.tasks import load_data,get_master_data
from core.models import BreezeAccount,Exchanges,Tick,Instrument,SubscribedInstruments,Candle,Percentage
from core.serializers import InstrumentSerializer
import urllib
# Create your views here.


def item_list(request):
    items = Candle.objects.all().order_by('-date')  
    context = {'items': items[:50]}
    return render(request, 'test.html', context)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_access_code(request):
    acc = BreezeAccount.objects.all().last()
    return Response("https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus(acc.api_key))

@api_view(['GET'])
@permission_classes([AllowAny])
def setup(request):
    get_master_data()
    timestamp = str(datetime.datetime.now()) #unique timestamp to identify all tasks from same instance
    per = Percentage.objects.create(source=timestamp,value=0)
    for exc in Exchanges.objects.all():
        load_data.delay(exc.id,timestamp)
    return Response({"working":"fine"})

@api_view(['GET'])
@permission_classes([AllowAny])
def subscribe_instrument(request,pk):
    id = pk
    ins = Instrument.objects.filter(id=pk)
    if not ins.exists():
        return Response({"error":"doesn't exist"})
    
    ins = ins[0]
    data = InstrumentSerializer(ins).data
    data.pop('id')
    ex_id = data.pop('exchange')
    if SubscribedInstruments.objects.filter(**data).exists():
        return Response({"error":"already subscribed"})
    
    sub_ins = SubscribedInstruments(exchange_id=ex_id,**data)
    sub_ins.save()

    return Response({"msg":"success",'data':InstrumentSerializer(sub_ins).data})
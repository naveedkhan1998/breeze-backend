import os
import zipfile
import shutil
import numpy as np
import urllib.request
from main.settings import MEDIA_ROOT
from celery.utils.log import get_task_logger
from celery import shared_task
from core.models import Exchanges,Instrument,Tick,SubscribedInstruments,Candle,Percentage
from datetime import datetime,time
from core.breeze import BreezeSession
logger = get_task_logger(__name__)


@shared_task(name='get_master_files')
def get_master_data():
    url = 'https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip'
    zip_path = MEDIA_ROOT+'SecurityMaster.zip'
    extracted_path = MEDIA_ROOT+'extracted/'
    try:
        shutil.rmtree(extracted_path)
    except:
        pass
    urllib.request.urlretrieve(url, zip_path)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extracted_path)

    for extracted_file in zf.namelist():
        #print("File:", extracted_file[:3])
        ins = Exchanges.objects.filter(title=extracted_file[:3])
        if ins.exists():
            ins.update(file='extracted/'+extracted_file)
        else:#first time
            title = extracted_file[:3]
            if title == 'BSE':
                new_ins = Exchanges(title=title,file='extracted/'+extracted_file,code='1',exchange='BSE')
                new_ins.save()
            if title == 'CDN':
                pass
            if title == 'FON':
                new_ins = Exchanges(title=title,file='extracted/'+extracted_file,code='4',exchange='NFO',is_option=True)
                new_ins.save()
            if title == 'NSE':
                new_ins = Exchanges(title=title,file='extracted/'+extracted_file,code='4',exchange='NSE')
                new_ins.save()

    
    os.remove(zip_path)
    #shutil.rmtree(extracted_path)

def count_check(count):
    if count<50:
        return True
    else:
        return False

@shared_task(name="load stocks") 
def load_data(id,timestamp):
    ins = Exchanges.objects.get(id=id)
    ins_list = []
    per = Percentage.objects.get(source=timestamp)
    counter = 0
    for line in ins.file:
        line = line.decode().split(',')
        data = [item.replace('"','')for item in line]
        if ins.is_option:# Futures and options
            if Instrument.objects.filter(token =data[0]).exists():
                pass
            else:
                if data[0] == 'Token':
                    pass
                else:
                    stock = Instrument(
                        exchange = ins,
                        stock_token = ins.code+'.1!'+data[0],
                        token=data[0],
                        instrument=data[1],
                        short_name=data[2],
                        series=data[3],
                        company_name=data[3],
                        expiry=datetime.strptime(data[4], '%d-%b-%Y').date(),
                        strike_price = float(data[5]),
                        option_type = data[6],
                        exchange_code=data[-1] if data[-1][-2:] != "\r\n" else data[-1][:-2]
                        )
                    ins_list.append(stock)
            if count_check(counter):
                counter += 1
            else:
                per.value += counter
                per.save()
                counter == 0
            
        else:# normal Stock
            if Instrument.objects.filter(token =data[0]).exists():
                pass
            else:
                if data[0] == 'Token':
                    pass
                else:
                    stock = Instrument(
                        exchange = ins,
                        stock_token = ins.code+'.1!'+data[0],
                        token=data[0],
                        short_name=data[1],
                        series=data[2],
                        company_name=data[3],
                        exchange_code=data[-1] if data[-1][-2:] != "\r\n" else data[-1][:-2]
                        )
                    ins_list.append(stock)
            if count_check(counter):
                counter += 1
            else:
                per.value += counter
                per.save()
                counter == 0
    our_array = np.array(ins_list)
    chunk_size = 800
    chunked_arrays = np.array_split(our_array, len(ins_list) // chunk_size + 1)
    chunked_list = [list(array) for array in chunked_arrays]
    for ch in chunked_list:
        Instrument.objects.bulk_create(ch)


@shared_task(name='websocket_start')
def websocket_start():
    sess = BreezeSession()
    sess.breeze.ws_connect()

    def on_ticks(ticks):
        tick_handler.delay(ticks)

    sess.breeze.on_ticks = on_ticks
    sub_ins = SubscribedInstruments.objects.all()
    if sub_ins.exists():
        for ins in sub_ins:
            sess.breeze.subscribe_feeds(stock_token=ins.stock_token)

    #sess.breeze.subscribe_feeds(stock_token="4.1!NIFTY 50")
    #sess.breeze.subscribe_feeds(stock_token="4.1!42697")

@shared_task(name='tick_handler')
def tick_handler(ticks):
    current_time = datetime.now()
    if current_time.time() >=time(hour=9,minute=15) and current_time.time()<=time(hour=15,minute=30):
        date = datetime.strptime(ticks['ltt'], '%a %b %d %H:%M:%S %Y')
        sub_ins = SubscribedInstruments.objects.get(stock_token=ticks['symbol'])
        tick = Tick(instrument=sub_ins,ltp=ticks['last'],date=date)
        tick.save()
    #else:
    #    pass

@shared_task(name='candle_maker')
def candle_maker():
    sub_ins = SubscribedInstruments.objects.all()
    if sub_ins.exists():
        for ins in sub_ins:
            sub_candle_maker.delay(ins.id)


@shared_task(name='sub_candle_maker')
def sub_candle_maker(ins_id):
    ticks = Tick.objects.filter(instrument_id=ins_id,used=False).order_by('date')
    if ticks.exists():
        for tick in ticks:
            candle_filter = Candle.objects.filter(instrument_id=ins_id,date=tick.date.replace(second=0,microsecond=0))
            if not candle_filter.exists():
                ins = SubscribedInstruments.objects.get(id=ins_id)
                Candle.objects.create(instrument=ins,date=tick.date.replace(second=0,microsecond=0),\
                                    open=tick.ltp,low=tick.ltp,close=tick.ltp,high=tick.ltp)
            else:#exists
                if candle_filter[0].low > tick.ltp:
                    candle_filter.update(low=tick.ltp,close=tick.ltp)

                if candle_filter[0].high < tick.ltp:
                    candle_filter.update(high=tick.ltp,close=tick.ltp)
                
                if candle_filter[0].high> tick.ltp >candle_filter[0].low :
                    candle_filter.update(close=tick.ltp)
    #ticks.update(used=True)
    ticks.delete()

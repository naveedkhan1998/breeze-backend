import os
import zipfile
import shutil
import numpy as np
import urllib.request
from main.settings import MEDIA_ROOT
from celery.utils.log import get_task_logger
from celery import shared_task
from core.models import (
    Exchanges,
    Instrument,
    Tick,
    SubscribedInstruments,
    Candle,
    Percentage,
    PercentageInstrument,
)
from datetime import datetime, time
from pytz import timezone
from datetime import datetime, timedelta
from core.helper import date_parser
from core.breeze import BreezeSession

logger = get_task_logger(__name__)


@shared_task(name="get_master_files")
def get_master_data():
    url = "https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip"
    zip_path = MEDIA_ROOT + "SecurityMaster.zip"
    extracted_path = MEDIA_ROOT + "extracted/"
    try:
        shutil.rmtree(extracted_path)
    except:
        pass
    urllib.request.urlretrieve(url, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extracted_path)

    for extracted_file in zf.namelist():
        # print("File:", extracted_file[:3])
        ins = Exchanges.objects.filter(title=extracted_file[:3])
        if ins.exists():
            ins.update(file="extracted/" + extracted_file)
        else:  # first time
            title = extracted_file[:3]
            if title == "BSE":
                new_ins = Exchanges(
                    title=title,
                    file="extracted/" + extracted_file,
                    code="1",
                    exchange="BSE",
                )
                new_ins.save()
            if title == "CDN":
                pass
            if title == "FON":
                new_ins = Exchanges(
                    title=title,
                    file="extracted/" + extracted_file,
                    code="4",
                    exchange="NFO",
                    is_option=True,
                )
                new_ins.save()
            if title == "NSE":
                new_ins = Exchanges(
                    title=title,
                    file="extracted/" + extracted_file,
                    code="4",
                    exchange="NSE",
                )
                new_ins.save()

    os.remove(zip_path)
    # shutil.rmtree(extracted_path)


def count_check(count, is_option=False):
    limit = 1000
    if is_option:
        limit = 30000
    if count < limit:
        return True
    else:
        return False


@shared_task(name="load stocks")
def load_data(id, exchange_name):
    ins = Exchanges.objects.get(id=id)
    ins_list = []
    per = Percentage.objects.get(source=exchange_name)
    counter = 0
    all_instruments = Instrument.objects.all()

    for line in ins.file:
        line = line.decode().split(",")
        data = [item.replace('"', "") for item in line]
        if ins.is_option:  # Futures and options
            # if all_instruments.filter(token=data[0]):
            #     pass
            # else:
            if data[0] == "Token":
                pass
            else:
                stock = Instrument(
                    exchange=ins,
                    stock_token=ins.code + ".1!" + data[0],
                    token=data[0],
                    instrument=data[1],
                    short_name=data[2],
                    series=data[3],
                    company_name=data[3],
                    expiry=datetime.strptime(data[4], "%d-%b-%Y").date(),
                    strike_price=float(data[5]),
                    option_type=data[6],
                    exchange_code=(
                        data[-1] if data[-1][-2:] != "\r\n" else data[-1][:-2]
                    ),
                )
                ins_list.append(stock)
            if count_check(counter, is_option=True):
                counter += 1
            else:
                per.value += counter
                per.save()
                counter == 0

        else:  # normal Stock
            # if all_instruments.filter(token=data[0]):
            #     pass
            # else:
            if data[0] == "Token":
                pass
            else:
                stock = Instrument(
                    exchange=ins,
                    stock_token=ins.code + ".1!" + data[0],
                    token=data[0],
                    short_name=data[1],
                    series=data[2],
                    company_name=data[3],
                    exchange_code=(
                        data[-1] if data[-1][-2:] != "\r\n" else data[-1][:-2]
                    ),
                )
                ins_list.append(stock)
            if count_check(counter):
                counter += 1
            else:
                value = 0
                if ins.title == "NSE":
                    value = (counter / 3837) * 100
                if ins.title == "BSE":
                    value = (counter / 10399) * 100
                per.value += value
                per.save()

    our_array = np.array(ins_list)
    chunk_size = 800
    chunked_arrays = np.array_split(our_array, len(ins_list) // chunk_size + 1)
    chunked_list = [list(array) for array in chunked_arrays]
    for ch in chunked_list:
        Instrument.objects.bulk_create(ch)


@shared_task(name="websocket_start")
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

    # sess.breeze.subscribe_feeds(stock_token="4.1!NIFTY 50")
    # sess.breeze.subscribe_feeds(stock_token="4.1!42697")


@shared_task(name="tick_handler")
def tick_handler(ticks):
    # Set the time zone to India
    india_tz = timezone("Asia/Kolkata")

    # Get the current time in India
    current_time_in_india = datetime.now(india_tz).time()

    # Check if it's within the market hours in India
    if time(9, 15) <= current_time_in_india <= time(15, 30):
        date = datetime.strptime(ticks["ltt"], "%a %b %d %H:%M:%S %Y")
        sub_ins = SubscribedInstruments.objects.get(stock_token=ticks["symbol"])
        tick = Tick(instrument=sub_ins, ltp=ticks["last"], date=date)
        tick.save()
    # else:
    #     pass


@shared_task(name="candle_maker")
def candle_maker():
    sub_ins = SubscribedInstruments.objects.all()
    if sub_ins.exists():
        for ins in sub_ins:
            sub_candle_maker.delay(ins.id)


@shared_task(name="sub_candle_maker")
def sub_candle_maker(ins_id):
    ticks = Tick.objects.filter(instrument_id=ins_id, used=False).order_by("date")
    if ticks.exists():
        for tick in ticks:
            candle_filter = Candle.objects.filter(
                instrument_id=ins_id, date=tick.date.replace(second=0, microsecond=0)
            )
            if not candle_filter.exists():
                ins = SubscribedInstruments.objects.get(id=ins_id)
                Candle.objects.create(
                    instrument=ins,
                    date=tick.date.replace(second=0, microsecond=0),
                    open=tick.ltp,
                    low=tick.ltp,
                    close=tick.ltp,
                    high=tick.ltp,
                )
            else:  # exists
                if candle_filter[0].low > tick.ltp:
                    candle_filter.update(low=tick.ltp, close=tick.ltp)

                if candle_filter[0].high < tick.ltp:
                    candle_filter.update(high=tick.ltp, close=tick.ltp)

                if candle_filter[0].high > tick.ltp > candle_filter[0].low:
                    candle_filter.update(close=tick.ltp)
    # ticks.update(used=True)
    ticks.delete()


@shared_task(name="individual candle loader")
def load_instrument_candles(id, user_id):

    sess = BreezeSession(user_id)
    qsi = SubscribedInstruments.objects.filter(id=id)

    if qsi.exists():
        ins = qsi.last()
        qs = Candle.objects.filter(instrument=ins).order_by("date")
        india_tz = timezone("Asia/Kolkata")

        # Get the current time in India
        end = datetime.now(india_tz)
        # end = datetime.now()
        start = end - timedelta(weeks=4)

        if qs.exists():
            start = qs.last().date

        if ins.expiry:
            expiry = datetime.now().replace(
                year=ins.expiry.year,
                month=ins.expiry.month,
                day=ins.expiry.day,
                hour=7,
                minute=0,
                second=0,
                microsecond=0,
            )
            data = fetch_historical_data(
                sess, start, end, ins.short_name, expiry, ins.stock_token, ins
            )
        else:
            data = fetch_historical_data(
                sess, start, end, ins.short_name, None, ins.stock_token, ins
            )

        if data:
            candle_list = []

            for item in data:
                date = datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S")
                date_compare = datetime.now().replace(
                    hour=9, minute=15, second=0, microsecond=0
                )

                if date.time() < date_compare.time():
                    continue
                else:
                    candle = Candle(
                        instrument=ins,
                        date=date,
                        open=item["open"],
                        close=item["close"],
                        low=item["low"],
                        high=item["high"],
                    )
                    candle_list.append(candle)

            our_array = np.array(candle_list)
            chunk_size = 800
            chunked_arrays = np.array_split(
                our_array, len(candle_list) // chunk_size + 1
            )
            chunked_list = [list(array) for array in chunked_arrays]

            for ch in chunked_list:
                Candle.objects.bulk_create(ch)


@shared_task(name="candles_loader")
def load_candles(user_id):
    sess = BreezeSession(user_id)
    sub_ins = SubscribedInstruments.objects.all()

    for ins in sub_ins:

        qs = Candle.objects.filter(instrument=ins).order_by("date")
        end = datetime.now()
        start = end - timedelta(weeks=4)

        if qs.exists():
            start = qs.last().date

        if ins.expiry:
            expiry = datetime.now().replace(
                year=ins.expiry.year,
                month=ins.expiry.month,
                day=ins.expiry.day,
                hour=7,
                minute=0,
                second=0,
                microsecond=0,
            )
            data = fetch_historical_data(
                sess, start, end, ins.short_name, expiry, ins.stock_token, ins
            )
        else:
            data = fetch_historical_data(
                sess, start, end, ins.short_name, None, ins.stock_token, ins
            )

        if data:
            candle_list = []

            for item in data:
                date = datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S")
                date_compare = datetime.now().replace(
                    hour=9, minute=15, second=0, microsecond=0
                )

                if date.time() < date_compare.time():
                    continue
                else:
                    candle = Candle(
                        instrument=ins,
                        date=date,
                        open=item["open"],
                        close=item["close"],
                        low=item["low"],
                        high=item["high"],
                    )
                    candle_list.append(candle)

            our_array = np.array(candle_list)
            chunk_size = 800
            chunked_arrays = np.array_split(
                our_array, len(candle_list) // chunk_size + 1
            )
            chunked_list = [list(array) for array in chunked_arrays]

            for ch in chunked_list:
                Candle.objects.bulk_create(ch)


def fetch_historical_data(
    session, start, end, short_name, expiry, stock_token, instrument
):
    """
    Fetch historical data from the API for the given instrument.
    """
    data = []
    current_start = start
    print("Start:", start)
    print("End:", end)
    print("Name:", short_name)
    per = PercentageInstrument.objects.get(instrument=instrument)
    per.percentage = 0
    per.is_loading = False
    per.save()
    diff: timedelta = end - start
    div = diff.days / 2

    while current_start < end:
        per.percentage += (1 / (div)) * 100
        per.save()
        current_end = min(current_start + timedelta(days=2), end)
        current_data = session.breeze.get_historical_data_v2(
            "1minute",
            date_parser(current_start),
            date_parser(current_end),
            short_name,
            "NFO" if expiry else ("NSE" if stock_token[0] == "4" else "BSE"),
            "futures" if expiry else None,
            date_parser(expiry) if expiry else None,
        )
        current_data = current_data.get("Success", [])

        if current_data:
            data.extend(current_data)

        current_start += timedelta(days=2)
    per.percentage = 100
    per.is_loading = True
    per.save()

    return data


@shared_task(name="resample_candles")
def resample_candles(candles, timeframe):
    """
    Resample candles to the given timeframe.
    """
    resampled_candles = []
    current_time = None
    current_candle = None

    for candle in candles:
        if current_time is None:
            current_time = candle.date
            current_candle = candle
        elif (candle.date - current_time).seconds >= (timeframe * 60):
            # Create a new candle with the aggregated values for the timeframe
            new_candle = Candle(
                instrument=current_candle.instrument,
                open=current_candle.open,
                high=max(current_candle.high, candle.high),
                low=min(current_candle.low, candle.low),
                close=candle.close,
                date=current_candle.date,
                is_active=current_candle.is_active,
            )
            resampled_candles.append(new_candle)

            # Reset for the new timeframe
            current_time = candle.date
            current_candle = candle
    # Include the last incomplete candle
    if current_candle:
        resampled_candles.append(current_candle)

    return resampled_candles

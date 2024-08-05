import os
import shutil
import zipfile
import numpy as np
import pandas as pd
import urllib.request
from pytz import timezone
from celery import shared_task
from core.helper import date_parser
from main.settings import MEDIA_ROOT
from core.breeze import BreezeSession
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta, time
from django.utils import timezone as django_timezone
from core.models import (
    Exchanges,
    Instrument,
    Tick,
    SubscribedInstruments,
    Candle,
    Percentage,
    PercentageInstrument,
)


logger = get_task_logger(__name__)


@shared_task(name="get_master_files")
def get_master_data():
    url = "https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip"
    zip_path = os.path.join(MEDIA_ROOT, "SecurityMaster.zip")
    extracted_path = os.path.join(MEDIA_ROOT, "extracted/")

    # Remove extracted directory if it exists
    if os.path.exists(extracted_path):
        shutil.rmtree(extracted_path)

    # Download the zip file
    urllib.request.urlretrieve(url, zip_path)

    # Extract the zip file
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extracted_path)

        for extracted_file in zf.namelist():
            exchange_title = extracted_file[:3]
            exchange_file_path = os.path.join("extracted", extracted_file)
            exchange_qs = Exchanges.objects.filter(title=exchange_title)

            if exchange_qs.exists():
                exchange_qs.update(file=exchange_file_path)
            else:
                # Create new exchange entry based on the title
                if exchange_title == "BSE":
                    new_exchange = Exchanges(
                        title=exchange_title,
                        file=exchange_file_path,
                        code="1",
                        exchange="BSE",
                    )
                elif exchange_title == "FON":
                    new_exchange = Exchanges(
                        title=exchange_title,
                        file=exchange_file_path,
                        code="4",
                        exchange="NFO",
                        is_option=True,
                    )
                elif exchange_title == "NSE":
                    new_exchange = Exchanges(
                        title=exchange_title,
                        file=exchange_file_path,
                        code="4",
                        exchange="NSE",
                    )
                else:
                    continue  # Skip entries that don't match any known exchange title

                new_exchange.save()

    # Clean up
    os.remove(zip_path)
    # Optionally remove the extracted files directory
    # shutil.rmtree(extracted_path)


@shared_task(name="load stocks")
def load_data(id, exchange_name):
    ins = Exchanges.objects.get(id=id)
    ins_list = []
    per = Percentage.objects.get(source=exchange_name)
    counter = 0
    all_instruments = set(
        Instrument.objects.filter(exchange=ins).values_list("token", "short_name")
    )

    lines = ins.file.read().decode().splitlines()
    total_lines = len(lines) - 1  # Subtract 1 to exclude header

    def count_check(count, is_option=False):
        limit = 1000
        if is_option:
            limit = 30000
        return count < limit

    for index, line in enumerate(lines):
        if index == 0:  # Skip header
            continue

        data = [item.replace('"', "") for item in line.split(",")]

        token_shortname_tuple = (data[0], data[1])
        if token_shortname_tuple in all_instruments:
            continue

        if ins.is_option:
            stock = Instrument(
                exchange=ins,
                stock_token=f"{ins.code}.1!{data[0]}",
                token=data[0],
                instrument=data[1],
                short_name=data[2],
                series=data[3],
                company_name=data[3],
                expiry=(
                    datetime.strptime(data[4], "%d-%b-%Y").date() if data[4] else None
                ),
                strike_price=float(data[5]),
                option_type=data[6],
                exchange_code=data[-1].strip(),
            )
        else:
            stock = Instrument(
                exchange=ins,
                stock_token=f"{ins.code}.1!{data[0]}",
                token=data[0],
                short_name=data[1],
                series=data[2],
                company_name=data[3],
                exchange_code=data[-1].strip(),
            )

        ins_list.append(stock)
        counter += 1

        # Update percentage after processing every 100 lines or when limit is reached
        if not count_check(counter, ins.is_option):
            per.value = (index / total_lines) * 100
            per.save()
            counter = 0

    # Final update to ensure percentage is correct
    per.value = 100
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
def load_instrument_candles(id, user_id, duration=4):

    sess = BreezeSession(user_id)
    qsi = SubscribedInstruments.objects.filter(id=id)

    if qsi.exists():
        ins = qsi.last()
        qs = Candle.objects.filter(instrument=ins).order_by("date")
        india_tz = timezone("Asia/Kolkata")

        # Get the current time in India
        end = datetime.now(india_tz)
        # end = datetime.now()
        start = end - timedelta(weeks=duration)

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
                        volume=item.get("volume", 0),
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
        per = PercentageInstrument.objects.filter(instrument=ins).first()
        per.percentage = 100
        per.is_loading = True
        per.save()


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
                        volume=item.get("volume", 0),
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
    session, start, end, short_name, expiry, stock_token, instrument: Instrument
):
    """
    Fetch historical data from the API for the given instrument.
    """
    data = []
    current_start = start
    print("Start:", start)
    print("End:", end)
    print("Name:", short_name)
    per = PercentageInstrument.objects.filter(instrument=instrument)
    if per.exists():
        per.delete()
    per = PercentageInstrument.objects.create(instrument=instrument)
    diff: timedelta = end - start
    div = diff.days / 2

    while current_start < end:
        per.percentage += (1 / (div)) * 100
        per.save()
        current_end = min(current_start + timedelta(days=2), end)
        if instrument.series == "OPTION":
            current_data = session.breeze.get_historical_data_v2(
                "1minute",
                date_parser(current_start),
                date_parser(current_end),
                short_name,
                "NFO" if expiry else ("NSE" if stock_token[0] == "4" else "BSE"),
                "options" if expiry else None,
                date_parser(expiry) if expiry else None,
                "call" if instrument.option_type == "CE" else "put",
                str(instrument.strike_price),
            )
        else:
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
    per.percentage = 90
    per.save()

    return data


@shared_task(name="resample_candles")
def resample_candles(candles, timeframe):
    """
    Resample candles to the given timeframe.
    """
    if not candles:
        return []

    resampled_candles = []
    current_time = datetime.fromisoformat(candles[0]["date"])
    next_time = current_time + timedelta(minutes=timeframe)
    current_open = candles[0]["open"]
    current_high = float("-inf")
    current_low = float("inf")
    current_close = None
    current_volume = 0
    current_day = current_time.date()

    for candle in candles:
        candle_date = datetime.fromisoformat(candle["date"])
        candle_day = candle_date.date()

        # Check if the day has changed
        if candle_day != current_day:
            # Include the last incomplete candle of the previous day
            resampled_candles.append(
                {
                    "open": current_open,
                    "high": current_high,
                    "low": current_low,
                    "close": current_close,
                    "volume": current_volume,
                    "date": current_time.isoformat(),
                }
            )
            # Reset for the new day
            current_time = candle_date
            next_time = current_time + timedelta(minutes=timeframe)
            current_open = candle["open"]
            current_high = candle["high"]
            current_low = candle["low"]
            current_volume = candle["volume"]
            current_close = candle["close"]
            current_day = candle_day
            continue

        if candle_date >= next_time:
            resampled_candles.append(
                {
                    "open": current_open,
                    "high": current_high,
                    "low": current_low,
                    "close": current_close,
                    "volume": current_volume,
                    "date": current_time.isoformat(),
                }
            )
            current_time = next_time
            next_time = current_time + timedelta(minutes=timeframe)
            current_open = candle["open"]
            current_high = candle["high"]
            current_low = candle["low"]
            current_volume = candle["volume"]
        else:
            current_high = max(current_high, candle["high"])
            current_low = min(current_low, candle["low"])
            current_volume += candle["volume"]

        current_close = candle["close"]

    # Include the last incomplete candle
    resampled_candles.append(
        {
            "open": current_open,
            "high": current_high,
            "low": current_low,
            "close": current_close,
            "volume": current_volume,
            "date": current_time.isoformat(),
        }
    )

    return resampled_candles

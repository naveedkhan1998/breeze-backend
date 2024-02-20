from core.models import Candle


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

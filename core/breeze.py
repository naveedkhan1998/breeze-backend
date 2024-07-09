from breeze_connect import BreezeConnect
from core.models import BreezeAccount, Instrument, Candle
from datetime import datetime, timedelta
from core.helper import date_parser
import numpy as np


class BreezeSession:
    def __init__(self, user_id):
        # if BREEZE_SESSION is None:
        self.acc = BreezeAccount.objects.get(user__id=user_id)
        self.breeze = BreezeConnect(api_key=self.acc.api_key)
        self.breeze.generate_session(
            api_secret=self.acc.api_secret, session_token=self.acc.session_token
        )
        # BREEZE_SESSION = self.breeze
        # else:
        # self.breeze = BREEZE_SESSION

    def get_data(self):
        pass
        """
        `data structure`:{
            'Error':None,
            'Status':200,
            'Success':{
                [
                    {
                        datetime:date str,
                        open:val,
                        high:val,
                        low:val,
                        close:val,
                        exchange_code:'NSE',
                        stock_code:'NIFTY',
                    },
                ]
            }
        }

        """
        # data = self.breeze.get_historical_data_v2('1minute','2023-07-01T07:00:00.000Z','2023-07-10T07:00:00.000Z','NIFTY','NSE')
        # data2 = self.breeze.get_historical_data_v2('1minute','2023-07-01T07:00:00.000Z','2023-07-10T07:00:00.000Z','NIFTY','NFO','futures','2023-07-27T07:00:00.000Z')
        # print(data)
        # sub_ins = Instrument.objects.all()
        # for ins in sub_ins:
        #    end = datetime.now()
        #    start = end - timedelta(weeks=1)
        #    if ins.is_future:
        #        expiry = datetime.now().replace(year=ins.expiry.year,month=ins.expiry.month,day=ins.expiry.day,\
        #                                        hour=7,minute=0,second=0,microsecond=0)
        #        data = self.breeze.get_historical_data_v2('1minute',date_parser(start),\
        #                                                  date_parser(end),'NIFTY','NFO',\
        #                                                    'futures',date_parser(expiry))
        #    else:
        #        data = self.breeze.get_historical_data_v2('1minute',date_parser(start),\
        #                                           date_parser(end),'NIFTY','NSE')
        #
        #    data = data['Success']
        #    candle_list = []
        #    for item in data:
        #        date = datetime.strptime(item['datetime'],'%Y-%m-%d %H:%M:%S')
        #        candle = Candle(date=date,open=item['open'],close=item['close'],\
        #                        low=item['low'],high=item['high'])
        #        candle_list.append(candle)
        #    our_array = np.array(candle_list)
        #    chunk_size = 800
        #    chunked_arrays = np.array_split(our_array, len(candle_list) // chunk_size + 1)
        #    chunked_list = [list(array) for array in chunked_arrays]
        #    for ch in chunked_list:
        #        Candle.objects.bulk_create(ch)

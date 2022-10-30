#!/usr/bin/python3
"""
    Copyright 2022 (C) Alexey Dynda

    This file is part of Binance Bot service.

    GNU General Public License Usage

    Binance Bot service is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Binance Bot service is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Binance Bot service.  If not, see <http://www.gnu.org/licenses/>.

"""


import logging
import signal
import requests
import time
#import OpenSSL
import hashlib
import hmac
import base64
import os
import configparser
import sys
import math
import strategies
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import argparse
import signal
import threading
import telegram
import binance

if not os.path.exists('.cache'):
    os.mkdir('.cache')

def millis():
    return round(time.time() * 1000)


parser = argparse.ArgumentParser(description='Trade help')
parser.add_argument("-a", "--asset",
                    help="list of assets using comma or CONFIG to read from config", required=False, default=None)
parser.add_argument("-q", "--history",
                    help="run on history data only, do not perform actual operations", required=False,
                    action="store_true", default=False)
parser.add_argument("-f", "--fake",
                    help="Run in realtime bot with fake operations", required=False,
                    action="store_true", default=False)
parser.add_argument("-s", "--stats",
                    help="Print trade stats, do not perform actual operations", required=False,
                    action="store_true", default=False)
parser.add_argument("-l", "--minutes",
                    help="show trades for last N minutes", required=False, type=int, default=720)
parser.add_argument('assetlist', nargs='?')
args = parser.parse_args()

requested_asset = args.asset
if args.assetlist is not None:
    requested_asset = args.assetlist

logFormatter = logging.Formatter("%(asctime)s [%(levelname)-4.4s]  %(message)s")
logger = logging.getLogger("trade")
logger.setLevel( logging.INFO )

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
consoleHandler.setLevel(logging.WARNING)
logger.addHandler(consoleHandler)

if requested_asset is None:
    fileHandler = logging.FileHandler("binance.log")
else:
    fileHandler = logging.FileHandler("binance-{}.log".format(requested_asset))
fileHandler.setFormatter(logFormatter)
fileHandler.setLevel(logging.INFO)
logger.addHandler(fileHandler)

g_api_key = ""
g_secret_key = ""

def rest_api(api, body, timestamp=True, signature=True, host="https://api.binance.com", operation='GET'):
    if timestamp:
        if body != "":
            body += "&"
        body += "timestamp={}".format(millis())
    if signature:
        #sig = OpenSSL.crypto.sign(g_secret_key, body, "sha256")
        message = bytes('the message to hash here', 'utf-8')
        secret = bytes('the shared secret key here', 'utf-8')
        hash = hmac.new(bytes(g_secret_key, 'utf-8'), bytes(body, 'utf-8'), hashlib.sha256)
        # to lowercase hexits
        hash.hexdigest()
        # to base64
        sig = hash.digest().hex()
        body += "&signature=" + sig
    if body != "":
        body = "?" + body
    retries = 10
    while retries > 0:
        try:
            retries -= 1
            # logger.warning(host + api + body)
            if operation == 'GET':
                result = requests.get(host + api + body, headers={"X-MBX-APIKEY": g_api_key})
            elif operation == 'DELETE':
                result = requests.delete(host + api + body, headers={"X-MBX-APIKEY": g_api_key})
            elif operation == 'POST':
                result = requests.post(host + api + body, headers={"X-MBX-APIKEY": g_api_key})
            result = result.json()
        except:
            result = None
        if result != None:
            break
    if result is None:
        logger.warning("{} FAILED!!!!".format(host + api + body))
    return result

#logger.warning(rest_api("/api/v3/ping", "", timestamp=False, signature=False));

#logger.warning(rest_api("/api/v3/avgPrice", "symbol=ADAUSDT", timestamp=False, signature=False));

#logger.warning(rest_api("/api/v3/account", "recvWindow=5000"));
# {'code': -1021, 'msg': 'Timestamp for this request is outside of the recvWindow.'}

green_emoji = u'\U0001F49A'
blue_emoji = u'\U0001F499'
red_emoji = u'\U0001F4A5'

class TradeCoin:
    def __init__(self, coin, pair):
        self._provider = binance.BinanceConnection(coin, pair, g_api_key, g_secret_key, logger)
        self._reset_virtual_money()
        self.__coin = coin
        self.__pair = pair
        self.__price = self._price();
        self.__free = 0
        self.__locked = 0
        self.__isup = False
        self.__stall_detected = False
        self.__stop_loss = 0
        self.__stop_loss_p = 0
        self.__take_profit = 0
        self.__minutes = "5m"
        self.__timeout = 50000 if self.__minutes == "1m" else 130000
        self.__trade_sum = 15
        self.__trade_amount = 0
        self.__order_color = "green"
        self.__strategy_name = "mixed"
        self.__max_boughts = 1
        self.__ma = {}
        self.__take_profit_k = 1.2
        self.__take_profit_levels = []
        self.__take_qty_levels = []
        self.__candles = []
        self.__dry_run = False
        self.__mode = "buying"
        self.__candle = strategies.ma.Candle( price = self.__price )
        self.__order_timer = 0
        self.__strategy = None
        self.__take_profit_armed = False
        self.__take_profit_extra_threshold = 0
        self.__sell_qty = 0
        self.__buy_qty = 0
        self.__sell_price = self.__price
        self.__buy_price = self.__price
        self._init_strategy()
        self.__order_id = None
        # https://api.binance.com/api/v3/klines?limit=10&interval=5m&symbol=THETAUSDT

    def _init_strategy(self):
        if self.__strategy_name == "ema5":
            self.__strategy = strategies.macross.MaCross(self, self.__price, 5, 10)
        if self.__strategy_name == "ema9":
            self.__strategy = strategies.macross.MaCross(self, self.__price, 9, 21)
        if self.__strategy_name == "ema10":
            self.__strategy = strategies.macross.MaCross(self, self.__price, 10, 20)
        if self.__strategy_name == "ema17":
            self.__strategy = strategies.macross.MaCross(self, self.__price, 17, 26)
        if self.__strategy_name == "macd":
            self.__strategy = strategies.macd.MacdSignal(self, self.__price, 4, 7, 6, 12)
            #self.__strategy = strategies.macd.MacdSignal(self, self.__price, 6, 12, 8, 18)
            # self.__strategy = strategies.macd.MacdSignal(self, self.__price, 8, 17, 12, 26)
        if self.__strategy_name == "mixed":
            self.__strategy = strategies.mixed.MixedTakeProfit(self, self.__price, strategies.macross.MaCross(self, self.__price, 5, 9, flat_checks = False))
        if self.__strategy_name == "stupid":
            self.__strategy = strategies.stupid.StupidTakeProfit(self, self.__price, strategies.macross.MaCross(self, self.__price, 5, 9, flat_checks = False))
        if self.__strategy_name == "mixed_adv":
            self.__strategy = strategies.mixed.AdvancedTakeProfit(self, self.__price )
        if self.__strategy_name == "mixed_exp":
            self.__strategy = strategies.mixed.AdvancedTakeProfitExp(self, self.__price )
        if self.__strategy_name == "new_vision":
            self.__strategy = strategies.new_vision.NewVision( self, self.__price, logger )
        if self.__strategy_name == "stepbystep":
            self.__strategy = strategies.step_by_step.StepByStep( self, self.__price, logger )

    def setLotSize( self, minQty, maxQty, stepSize ):
        self._provider.setLotSize( minQty, maxQty, stepSize )
        self.__minqty = minQty
        self.__maxqty = maxQty
        self.__stepSize = stepSize

    def setQuantity(self, free, locked):
        self.__free = free
        self.__locked = locked
        # self.__mode = "selling" if self.__free > self.__stepSize else "buying"

    def setDryRun(self):
        self._provider.setDryRun()
        self.__dry_run = True

    def is_dry_run(self):
        return self.__dry_run

    def load_config( self ):
        config = configparser.ConfigParser()
        config.read( '.cache/' + self.__pair ) # len > 0
        #if config.has_option('main', 'dry_run'):
        #     self.__dry_run = config.getboolean('main', 'dry_run')
        if config.has_option('main', 'last_trend'):
             self.__last_trend = config.getfloat('main', 'last_trend')
        if config.has_option('main', 'last_sell_trend'):
             self.__last_sell_trend = config.getfloat('main', 'last_sell_trend')
        if config.has_option('main', 'mode'):
             self.__mode = config.get('main', 'mode')
        if config.has_option('main', 'stop_loss'):
             self.__stop_loss = config.getfloat('main', 'stop_loss')
        if config.has_option('main', 'stop_loss_p'):
             self.__stop_loss_p = config.getfloat('main', 'stop_loss_p')
        if config.has_option('main', 'take_profit'):
             self.__take_profit = config.getfloat('main', 'take_profit')
        if config.has_option('main', 'minutes'):
             self.__minutes = config.get('main', 'minutes')
        if config.has_option('main', 'trade_sum'):
             self.__trade_sum = config.getint('main', 'trade_sum')
        if config.has_option('main', 'trade_amount'):
             self.__trade_amount = config.getfloat('main', 'trade_amount')
        if config.has_option('main', 'profit_armed'):
             self.__take_profit_armed = config.getboolean('main', 'profit_armed')
        if config.has_option('main', 'profit_threshold'):
             self.__take_profit_extra_threshold = config.getfloat('main', 'profit_threshold')
        if config.has_option('main', 'strategy'):
             self.__strategy_name = config.get('main', 'strategy')
        if config.has_option('main', 'max_boughts'):
             self.__max_boughts = config.getint('main', 'max_boughts')
        if config.has_option('main', 'virtual_usdt'):
             self.__virtual_usdt = config.getfloat( 'main', 'virtual_usdt' )
        if config.has_option('main', 'virtual_coin'):
             self.__virtual_coin = config.getfloat( 'main', 'virtual_coin' )
        if config.has_option('main', 'virtual_total'):
             self.__virtual_total = config.getfloat( 'main', 'virtual_total' )
        if config.has_option('main', 'order_id'):
             self.__order_id = config.get( 'main', 'order_id' )
             if self.__order_id == "":
                 self.__order_id = None
        self.__take_profit_levels = []
        self.__take_qty_levels = []
        i = 0
        while config.has_option('main', "profit_level{}".format(i)):
            self.__take_profit_levels.append( config.getfloat('main', "profit_level{}".format(i)) )
            i += 1
        i = 0
        while config.has_option('main', "qty_level{}".format(i)):
            self.__take_qty_levels.append( config.getfloat('main', "qty_level{}".format(i)) )
            i += 1
        #self.__take_profit_levels.sort(reverse=True)
        #self.__take_qty_levels.sort(reverse=True)
        self._init_strategy()
        if self.__strategy is not None:
            self.__strategy.load_config( config )
        self.__timeout = 50000 if self.__minutes == "1m" else 120000

    def save_config(self):
        config = configparser.ConfigParser(allow_no_value=True)
        config.add_section( 'main' )
        #config['main']['dry_run'] = str(self.__dry_run)
        config['main']['mode'] = str(self.__mode)
        config.set('main','; Maximum number of allowed boughts without sell')
        config['main']['max_boughts'] = str(self.__max_boughts)
        config.set('main','; Current stop loss value')
        config['main']['stop_loss'] = str(self.__stop_loss)
        config['main']['stop_loss_p'] = str(self.__stop_loss_p)
        config.set('main','; This setting is just for internal calculations and not used in trades')
        config['main']['take_profit'] = str(self.__take_profit)
        config.set('main','; This is depth of the candle bars in minutes or hours')
        config.set('main','; Trading with 1m depth is dangerous and not good because of the fees')
        config.set('main','; Different values affect strategy settings')
        config.set('main','; Valid values are: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1D, 3D, 1w, 1M')
        config['main']['minutes'] = str(self.__minutes)
        config.set('main','; Quotes of basic asset like USDT you want to spend on each transaction')
        config.set('main','; Less value is less income and less risk')
        config['main']['trade_sum'] = str(self.__trade_sum)
        config['main']['trade_amount'] = str(self.__trade_amount)
        config.set('main','; Strategy name to use while trading')
        config.set('main','; "mixed", "mixed_exp" "ema10" strategies are the best ones for now, but it cannot make much profit on high grow')
        config.set('main','; ema10 is good at 15m depth')
        config.set('main','; Valid values are: ema5, ema9, ema10, macd, mixed')
        config['main']['strategy'] = str(self.__strategy_name)
        config.set('main','; These arguments have no meaning for real sales, they are just for convenience')
        config['main']['virtual_usdt'] = str(self.__virtual_usdt)
        config['main']['virtual_coin'] = str(self.__virtual_coin)
        config['main']['virtual_total'] = str(self.__virtual_total)
        if self.__order_id == None:
            config['main']['order_id'] = ""
        else:
            config['main']['order_id'] = str(self.__order_id)

        config['main']['profit_armed'] = str(self.__take_profit_armed)
        config['main']['profit_threshold'] = str(self.__take_profit_extra_threshold)
        for i in range(len(self.__take_profit_levels)):
            config['main']["profit_level{}".format(i)] = str(self.__take_profit_levels[i])
        for i in range(len(self.__take_qty_levels)):
            config['main']["qty_level{}".format(i)] = str(self.__take_qty_levels[i])
        if self.__strategy is not None:
            self.__strategy.save_config( config )
        config.write(open('.cache/' + self.__pair, "w"))

    def get_ma(self, name):
        return self.__ma[name]

    def get_candles(self):
        return self.__candles

    def get_candle(self):
        return self.__candle

    def get_mode(self):
        return self.__mode

    def set_mode(self, mode):
        self.__mode = mode

    def price(self):
        return self.__price

    def take_profit_k(self):
        return self.__take_profit_k

    def _price(self):
        return self._provider.price()

    def _reset_virtual_money(self):
        self.__virtual_usdt = 100
        self.__virtual_coin = 0
        self.__virtual_total = 0

    def has_something_to_sell(self):
        return len( self.__take_profit_levels ) > 0

    def can_buy_more(self):
        return len( self.__take_profit_levels ) < self.__max_boughts

    def _set_take_profit(self, profit, qty = 0):
        # if we have history with other take profit buy
        self.__take_profit_levels.append(profit)
        self.__take_qty_levels.append( qty )
        # Pop up the most cheap to the top
        #self.__take_profit_levels.sort(reverse=True)
        self.__take_profit_armed = False
        self.__take_profit_extra_threshold = 0

    def _get_take_profit(self, noupdate = False):
        if len(self.__take_profit_levels) == 0:
            return 0
        if not noupdate:
            i = 10
        return self.__take_profit_levels[-1]

    def  _get_qty_profit(self):
        if len(self.__take_qty_levels) == 0:
            return None
        return self.__take_qty_levels[-1]

    def _cooldown_take_profit(self, ignore_armed_flag = False):
        if self.__take_profit_armed or ignore_armed_flag:
            self.__take_profit_armed = False
            if len(self.__take_profit_levels) > 0:
                profit = self.__take_profit_levels[-1]
                self.__take_profit_levels[-1] = self.__take_profit_levels[-1] * 0.997
                logger.warning("[{}] Profit is cooled down from {} to {}".format(self.__pair, profit, self.__take_profit_levels[-1]))

    def _update_take_profit(self, price):
        profit = self._get_take_profit(self)
        if profit == 0:
            return False
        if not self.__take_profit_armed or self.__dry_run:
            if price > profit:
                if not self.__dry_run:
                    self.__take_profit_levels[-1] = price
                else:
                    return True
                # Needed to avoid False positives
                self.__take_profit_extra_threshold = 0.0010 * price + ( price - profit ) * 0.10
                self.__take_profit_armed = True
                logger.warning("[{}] ARMED: {}".format( self.__pair, self.__take_profit_levels[-1] ))
        if self.__take_profit_armed and profit > 0:
            if price > profit:
                self.__take_profit_extra_threshold += ( price - profit ) * 0.10
                self.__take_profit_levels[-1] = price
            elif price < (profit - self.__take_profit_extra_threshold):
                logger.warning("[{}] It's time to sell at {} (price) ~ {} (profit) - {} (threshold)".format(self.__pair, price, profit, self.__take_profit_extra_threshold))
                return True
        return False

    def _close_take_profit(self, all = False):
        while True:
            self.__take_profit_armed = False
            if self.__strategy is not None:
                if len( self.__take_profit_levels ) > 0:
                    # self.__stop_loss = assetusdt * 0.90
                    self.__take_profit_levels.pop()
                    # self.__take_qty_levels.pop()
            if not all:
                break
            if len( self.__take_profit_levels ) == 0:
                break
        while True:
            if len( self.__take_qty_levels ) > 0:
                self.__take_qty_levels.pop()
            if not all:
                break
            if len( self.__take_qty_levels ) == 0:
                break

    def _place_sell_order(self, price, quote):
        if not self.has_something_to_sell():
            logger.error("[{}] ------ CRITICAL: Nothing to sell".format(self.__pair))
            self.__strategy.on_sell(success=False)
            return False
        order = self._provider.place_sell_order( price, quote )
        if order is None:
            self.__strategy.on_sell(success=False)
            return False
        self.__order = order
        self.__mode = "waiting for sell"
        return True

    def _place_buy_order(self, index, quote, price, stop_loss, take_profit, stop_loss_p = 0):
        if len( self.__take_profit_levels ) >= self.__max_boughts:
            logger.error("[{}] ------ Cannot buy anymore, limit of boughts is reached: {}".format( self.__pair, self.__max_boughts))
            self.__strategy.on_buy(success=False)
            return False
        order = self._provider.place_buy_order( price, quote )
        if order is None:
            self.__strategy.on_buy(success=False)
            return False
        logger.warning("[{}] >>> stop_loss at {}, take profit at {}".format( self.__pair, stop_loss, take_profit))
        self.__order = order
        self.__mode = "waiting for buy"
        return True

    def char_status(self):
        status = ""
        if self.__isup:
            status += "^"
        else:
            status += '-'
        return status

    def name(self):
        return self.__coin

    def pair(self):
        return self.__pair

    def trade_amount(self):
        return self.__trade_amount

    def _request_amount(self):
        if self.__dry_run:
            self.__free = self.__virtual_coin
            self.__locked = 0
            return
        balance = rest_api('/api/v3/account', '')
        for b in balance["balances"]:
            if b["asset"] == self.__coin:
                logger.warning("[{}] {}".format(self.__pair, b["asset"]))
                locked = float(b["locked"])
                free = float(b["free"])
                count = locked + free
                self.__locked = locked
                self.__free = free
                break

    def _waiting_for_sell(self):
        # If price is wrong just exit
        if self.__order.status() == "completed":
            self.__stop_loss = 0
            self.__stop_loss_p = 0
            self.__virtual_usdt += self.__order.qty() * self.__order.price() * 0.999
            self.__virtual_coin -= self.__order.qty()
            self._request_amount()
            # print("XXXXXXXXXXXXXXXXXXX", self.__virtual_usdt)
            self.__virtual_total = self.__virtual_usdt + self.__free * self.__order.price()
            logger.warning("[{}] ******** Successfully sold, total {}, expected USDT ~: {}, virtual USDT ~ {}".format(
                        self.__pair, self.__free + self.__locked, self.__virtual_total, self.__virtual_usdt))
            if not self.__dry_run:
                if self.__order_color == "red":
                    telegram.telegram_send( red_emoji + " SELL {} {} at {} ".format(self.__order.qty(), self.__pair, self.__order.price()))
                else:
                    telegram.telegram_send( blue_emoji + " SELL {} {} at {} ".format(self.__order.qty(), self.__pair, self.__order.price()))
            self._close_take_profit()
            self.__mode = "buying"
            self.__order = None
            self.__strategy.on_sell(success=True)
            return
        logger.warning("[{}] ******** Selling asset is in progress".format(self.__pair))
        # if no sell for 20 seconds
        if self.__order.time_passed() > self.__timeout:
            self.__order.cancel()
            self._cooldown_take_profit()
            logger.warning("[{}] ******** Selling is cancelled".format(self.__pair))
            self.__mode = "selling"
            self.__order = None
            self._request_amount()
            self.__strategy.on_sell(success=False)

    def _waiting_for_buy(self):
        if self.__order.status() == "completed":
            self.__virtual_usdt -= (self.__order.qty() * self.__order.price()) * 1.001
            self.__virtual_coin += self.__order.qty()
            self._request_amount()
            if self.__free < self.__order.qty() / 2: ### WHAAAT ??
                self._request_amount()
            self.__virtual_total = self.__virtual_usdt + self.__free * self.__order.price()
            logger.warning("[{}] ******** Successfully bought, total {}, expected USDT ~: {}, virtual USDT ~ {}".format(
                        self.__pair, self.__free + self.__locked, self.__virtual_total, self.__virtual_usdt))
            self._set_take_profit( self.__take_profit, self.__order.qty() )
            if not self.__dry_run:
                telegram.telegram_send( green_emoji + " BUY {} {} at {} ".format(self.__order.qty(), self.__pair, self.__order.price()))
            self.__mode = "selling"
            self.__order = None
            self.__strategy.on_buy(success=True)
            return
        logger.warning("[{}] ******** Buying asset is in progress".format(self.__pair))
        # if no buy for 20 seconds
        if self.__order.time_passed() > self.__timeout:
            self.__order.cancel()
            logger.warning("[{}] ******** Buying is cancelled".format(self.__pair))
            self._request_amount()
            self.__mode = "buying"
            self.__order = None
            self.__strategy.on_buy(success=False)

    def eat_candle(self, candle):
        self.__candles.append( candle )
        if self.__strategy is not None:
            self.__strategy.eat_candle( candle )

    def _get_ma_cross(self, index, ma_fast, ma_slow):
        last_trend = ma_fast.median(index - 1) - ma_slow.median( index - 1)
        trend = ma_fast.median(index) - ma_slow.median( index )
        if last_trend > 0 and trend < 0:
            return "SELL"
        if last_trend < 0 and trend > 0:
            return "BUY"
        return "WAIT"

    def _get_ma_decision(self, index, ma_fast, ma_slow):
        ma_trend = self._get_ma_cross( index, ma_fast, ma_slow)
        if ma_trend == "SELL" and self.__candles[index].close > ma_fast.median(index):
            return "WAIT"
        ma_trend_1 = self._get_ma_cross( index - 1, ma_fast, ma_slow)
        if ma_trend_1 == "SELL" and self.__candles[index].close < ma_fast.median(index):
            return "SELL"
        if ma_trend == "BUY" and ma_trend_1 == "SELL":
            return "WAIT"
        return ma_trend

    def get_prediction(self, index = -1, strategy = "default"):

        if self.__strategy:
            return self.__strategy.get_decision(index)

        # Index points to the time back, we want to get prediction
        return ("WAIT", 0, 0, 0)

    def read_candles(self):
        candles = rest_api("/api/v3/klines", "symbol={}&limit=1000&interval={}".format( self.__pair, self.__minutes ), timestamp=False, signature=False )
        for c in candles[:-1]:  # Last candle is still open
            candle = strategies.ma.Candle( candle = c )
            self.eat_candle( candle )

    def print_trade_stats(self, limit=1000, minutes = None):
        if minutes is None:
            minutes = 12 * 60
        start_time = millis() - minutes * 60 * 1000  # Last 12 hours
        print("-----------------------  {}  -----------------------".format(self.name()))
        trades = rest_api("/api/v3/myTrades", "symbol={}&limit={}&startTime={}".format( self.__pair, limit, int(start_time) ))
        delta_usdt = 0
        delta_asset = 0
        delta_commission = 0
        total = 0
        cnt_buy = 0
        for t in trades:
            # print(t)
            price = float(t["price"])
            qty = float(t["qty"])
            quote = float(t["quoteQty"])
            commission = float(t["commission"])
            commissionAsset = t["commissionAsset"]
            tt=time.localtime(int(t["time"])/1000.0)
            isBuyer = bool(t["isBuyer"])
            isMaker = bool(t["isMaker"])
            operation = "----"
            old_total = total
            if isBuyer:
                cnt_buy += qty
                if commissionAsset != "BNB":
                    delta_asset += qty  # qty - commission
                    delta_commission += commission * price
                else:
                    delta_asset += qty
                delta_usdt -= qty * price
                operation = "BUY "
            else:
                if cnt_buy > 0:
                    cnt_buy = max(cnt_buy - qty, 0)
                    delta_asset -= qty
                    if commissionAsset != "BNB":
                        delta_usdt += (qty * price) # delta_usdt += (qty * price - commission)
                        delta_commission += commission
                    else:
                        delta_usdt += (qty * price)  # TODO: Commission must be recalculated from BNB
                operation = "SELL"
            total = delta_asset * price + delta_usdt
            print(".... {} {} {} QTY:{}, PRICE:{} COM: {} {}....... TOTAL:{} (PNL:{})".format(
                time.asctime(tt), operation, self.name(), qty, price, commission, commissionAsset, total, total - old_total))
        print("Total result: {} = income {} + commission {}".format( total, total - delta_commission, delta_commission))
        return (total, delta_commission)

    def dry_run(self):
        self.__dry_run = True
        self._provider.setDryRun()
        if self.__strategy is not None:
            self.__strategy.reset_boughts()
        x = 0
        fig = plt.figure(figsize=(100.0,10.0), dpi=172.0)
        plt.rcParams['axes.facecolor'] = 'black'
        for i in range( -len( self.__candles) + 10, 0):
            result = self.update(i)
            if result[0] != "":
                print("== {} {}".format( result[0], result[1] ))
            x += 1
            if self.__strategy is not None:
                self.__strategy.draw( x, i, plt )
            plt.bar(x, abs(self.__candles[i].open - self.__candles[i].close),
                    width = 0.9, bottom = min(self.__candles[i].open, self.__candles[i].close),align='center',
                    color="green" if self.__candles[i].is_green() else "red" )
            plt.plot([x,x], [self.__candles[i].high, self.__candles[i].low], linewidth=0.2, color="green" if self.__candles[i].is_green() else "red")
            if result[0] != "":
                 logger.warning("[{}] {} hours ago".format(self.__pair, round(i * int(self.__minutes[:-1]) / 60, 0)) )
            if result[0] == "BUY":
                plt.annotate( "buy {}".format( result[1] ), (x + 1,result[1]), xytext=(0,-50), textcoords='offset points', ha='center', color="lime",
                              bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.4), arrowprops=dict(arrowstyle='->', color="lime", shrinkB=0), fontsize=6 )
            if result[0] == "SELL" or result[0] == "LOSS" or result[0] == "TAKE":
                plt.annotate( "{} {}".format( result[0].lower(),result[1] ), (x + 1,result[1]), xytext=(0,+50), textcoords='offset points', ha='center', color="red",
                              bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.4), arrowprops=dict(arrowstyle='->', color="orangered", shrinkB=0), fontsize=6 )

        plt.xlabel('bars')
        plt.ylabel('price')
        plt.title( "{} - {} ({} USDT)".format( self.__pair, self.__strategy_name, self.__virtual_total ) )
        plt.savefig("graph_{}_{}.png".format(self.__pair, self.__strategy_name))

    def print_stats(self):
        s = '... state: {} {}={}, stop_loss={}, take_profit={} armed={}'.format(self.__mode,
                self.__pair, round(self.__price,6),
                self.__stop_loss, self._get_take_profit(noupdate=True), self.__take_profit_armed)
        #logger.warning("[{}] {}".format(self.__pair, s))

    def sell_state(self, index):
        ( prediction, price, stop_loss, take_profit ) = self.get_prediction( index, self.__strategy_name )
        # Check sell requirements and if we have something to sell
        if prediction == "SELL":
            self.__order_color = "blue"
            if self._place_sell_order(price, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price):
                return ("SELL", price)
        if prediction == "FORCE_BUY":
            if type(stop_loss) == str:
                perc = float(stop_loss.split(':')[1])
                stop_loss = float(stop_loss.split(':')[0])
            else:
                perc = 0
            self.__order_color = "green"
            if self._place_buy_order(index, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price, price, stop_loss, take_profit, stop_loss_p=perc):
                return ("BUY", price)
        if prediction == "LOSS":
            self.__order_color = "red"
            if self._place_sell_order(price, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price):
                return ("LOSS", price)
        if prediction == "TAKE":
            self.__order_color = "blue"
            if self._place_sell_order(price, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price):
                return ("TAKE", price)
        return ("",0)

    def buy_state(self, index):
        # Check buy requirements
        ( prediction, price, stop_loss, take_profit ) = self.get_prediction( index, self.__strategy_name )
        if prediction == "BUY" or prediction == "FORCE_BUY":
            if type(stop_loss) == str:
                perc = float(stop_loss.split(':')[1])
                stop_loss = float(stop_loss.split(':')[0])
            else:
                perc = 0
            self.__order_color = "green"
            if self._place_buy_order(index, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price, price, stop_loss, take_profit, stop_loss_p=perc):
                return ("BUY", price)
        if prediction == "LOSS":
            self.__order_color = "red"
            if self._place_sell_order(price, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price):
                return ("LOSS", price)
        if prediction == "TAKE":
            self.__order_color = "blue"
            if self._place_sell_order(price, self.__trade_sum if self.__trade_amount == 0 else self.__trade_amount * price):
                return ("TAKE", price)
        return ("",0)

    def update(self, index = -1):
        if index == 0:
            candles = rest_api("/api/v3/klines", "symbol={}&limit=2&interval={}".format( self.__pair, self.__minutes ), timestamp=False, signature=False)
            if candles == None:
                return ("", 0)
            self.__price = self._price()
            candle = strategies.ma.Candle( candle = candles[0] )
            self.__candle = strategies.ma.Candle( candle = candles[1] )
            if candle.open_time >= self.__candles[-1].close_time:
                self.eat_candle( candle )
                index = -1

        if index == -1:
            self.print_stats()

        if self.__mode == "waiting for sell":
            self._waiting_for_sell()
            return ("", 0)
        if self.__mode == "waiting for buy":
            self._waiting_for_buy()
            return ("", 0)

        # This protection works always, no matter the mode is
        current_sell_price = self.__candles[index + 1].low if index < -1 else self.price()
        current_buy_price =  max(self.__candles[index + 1].open, self.__candles[index + 1].close) if index < -1 else self.price()
        if self.__stop_loss > 0:
            if current_sell_price < self.__stop_loss:
                if self.__strategy is None or self.__strategy.sell_on_stop_loss():
                    result = ("LOSS", self.__stop_loss)
                    self._place_sell_order(self.__stop_loss, self.__trade_sum)
                    return result
                self.__mode = "buying"
                self.__stop_loss = 0
                self.__stop_loss_p = 0
            if current_sell_price > self.__stop_loss:
                self.__stop_loss = max( self.__stop_loss, current_sell_price * self.__stop_loss_p )

        if self._update_take_profit( current_buy_price ):
            result = ("TAKE", current_buy_price)
            self._place_sell_order(current_buy_price, self.__trade_sum)
            return result

        if self.__mode == "selling":
            return self.sell_state(index)
        elif self.__mode == "buying":
            return self.buy_state(index)
        return ("",0)


exchangeinfo = rest_api("/api/v3/exchangeInfo", "", timestamp=False, signature=False)

tracked = []
coins =""

config = configparser.ConfigParser()
if len( config.read( 'config.ini')) > 0:
    if config.has_option('main', 'api'):
        g_api_key = config.get('main', 'api')
    if config.has_option('main', 'secret'):
        g_secret_key = config.get('main', 'secret')
    if requested_asset == "CONFIG":
        coins = config.get('main', 'coins').split(',')
        requested_asset = None
    if config.has_option('main', 'telegram_bot_token'):
        telegram_bot_token = config.get('main', 'telegram_bot_token')
    if config.has_option('main', 'telegram_chat_id'):
        telegram_chat_id = config.get('main', 'telegram_chat_id' )
    telegram.config_telegram( telegram_bot_token, telegram_chat_id )

balance = rest_api('/api/v3/account', '')
usdtrub = float(rest_api("/api/v3/ticker/price", "symbol=USDTRUB", timestamp=False, signature=False)['price'])
wallet_balance = 0

if requested_asset is not None:
    coins = requested_asset.split(',')

for c in coins:
    obj = TradeCoin( c, config.get(c,'pair') )
    obj.load_config()
    obj.read_candles()
    for a in exchangeinfo["symbols"]:
        if a["symbol"] == config.get(c,'pair'):
            for f in a["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    obj.setLotSize( float(f["minQty"]), float(f["maxQty"]), float(f["stepSize"]) )
    for b in balance["balances"]:
        if b["asset"] == c:
            locked = float(b["locked"])
            free = float(b["free"])
            count = locked + free
            value = count * obj.price()
            obj.setQuantity( free, locked )
            logger.warning( "[{}] Asset {} {} ({} USDT,  {} RUB)".format(config.get(c,'pair'), c, count, value, value * usdtrub))
            wallet_balance += value * usdtrub
    tracked.append( obj )

logger.warning("================================")
logger.warning("Wallet assets balance: {} RUB".format(wallet_balance))
logger.warning("================================")

if args.history:
    for i in tracked:
        i.setQuantity( 0, 0 )
        i._close_take_profit(all=True)
        i._reset_virtual_money()
        i.dry_run()
    exit(0)

if args.stats:
    total = 0
    commission = 0
    for i in tracked:
        temp = i.print_trade_stats(minutes = args.minutes)
        total += temp[0]
        commission += temp[1]
    print("========================================")
    print("All assets income balance: {} = income {} + commission {} (USDT)".format( total, total - commission, commission ))
    exit(0)

if args.fake:
    for i in tracked:
        i.setDryRun()

exit_requested = False

def exit_gracefully(signum, frame):
    global exit_requested
    logger.error("SIGTERM received")
    exit_requested = True

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)

def coin_thread( obj ):
    global exit_requested
    if not obj.is_dry_run():
        logger.warning("[{}] WARNING: ACTIVE TRADE MODE FOR {}".format(obj.pair(), obj.name()))
    try:
        while not exit_requested:
            obj.update(0)
            time.sleep( 0.5 )
    except ( Exception, KeyboardInterrupt ) as e:
        obj.save_config()
        exit_requested = True
        logger.warning(e)
        # raise


threads = []
if len(tracked) > 1:
    for c in tracked:
        thread = threading.Thread(target = coin_thread, args = (c, ))
        thread.start()
        threads.append( thread )

    while not exit_requested:
        time.sleep( 1 )
        pass

    for thread in threads:
        thread.join()
else:
    coin_thread( tracked[0] )
#except ( Exception, KeyboardInterrupt ) as e:
#    for c in tracked:
#        c.save_config()
#    logger.warning("Main thread interrupted")
#    logger.warning(e)
#    logging.shutdown()
#    raise

logger.warning("Main thread interrupted")
for c in tracked:
    c.save_config()
logging.shutdown()

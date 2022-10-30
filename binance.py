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
import sys
import math
import strategies
import argparse

def millis():
    return round(time.time() * 1000)

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

green_emoji = u'\U0001F49A'
blue_emoji = u'\U0001F499'
red_emoji = u'\U0001F4A5'


class Order:
    def __init__(self, connection, pair, id):
        self._connection = connection
        self.__pair = pair
        self.__id = id
        self.__order_timer = millis()
        self._qty = 0
        self._price = 0

    def status(self):
        if self._connection._dry_run:
            return "completed"
        result = rest_api("/api/v3/openOrders", "symbol={}".format(self.__pair))
        if result is None:
            return "active"
        for a in result:
            if a["orderId"] == self.__id:
                return "active"
        return "completed"

    def cancel(self):
        if self._connection._dry_run:
            return []
        if self.__id is not None:
            result = rest_api("/api/v3/order", "symbol={}&orderId={}".format(self.__pair, self.__id), operation="DELETE")
        return result

    def price(self):
        return self._price

    def qty(self):
        return self._qty

    def time_passed(self):
        return millis() - self.__order_timer


class BinanceConnection:
    def __init__(self, coin, pair, api_key, secret_key, logger = None):
        global g_api_key
        global g_secret_key
        g_api_key = api_key
        g_secret_key = secret_key
        self.__coin = coin
        self._dry_run = False
        self.__pair = pair
        self.__price = self.price();
        self.__minutes = "5m"
        self.__timeout = 50000 if self.__minutes == "1m" else 130000
        self.__minqty = 0.1
        self.__maxqty = 10
        self.__stepSize = 0.01
        self.__sell_qty = 0
        self.__buy_qty = 0
        self.__logger = logger

    def setDryRun(self):
        self._dry_run = True

    """
        Returns current ticker price
    """
    def price(self):
        if self.__pair == "USDTUSDT":
            return 1.0
        p = rest_api("/api/v3/ticker/price", "symbol={}".format(self.__pair), timestamp=False, signature=False)
        # p = rest_api("/api/v3/avgPrice", "symbol={}".format(self.__pair), timestamp=False, signature=False)
        if 'price' not in p.keys():
            return 0
        return float(p['price'])

    """
        Sets lot size (minmum, maximum, stepSize)
    """
    def setLotSize( self, minQty, maxQty, stepSize ):
        self.__minqty = minQty
        self.__maxqty = maxQty
        self.__stepSize = stepSize

    """
        Places any order. This is private function
        Returns order id
    """
    def _place_order(self, sell_buy, price, limit = "LIMIT", quote = 0):
        #print( sell_buy, price, limit, quote, asset)
        if price is None or price == 0:
            logger.warning("[{}] !!! No price".format(self.__pair))
            return None
        # quantity is how much of asset you want to sell or buy
        # quoteOrderQty is how much you want to spend buying or selling
        precision = 4
        div = 1
        while price / div > 10:
            precision -= 1
            div = div * 10
        mult = 1
        while price * mult < 1:
            precision += 1
            mult = mult * 10
        actual_price = round(price * 1.0, precision)
        qty = round( self.__minqty +  math.floor((quote / price - self.__minqty) / self.__stepSize) * self.__stepSize, 8 )
        self.__place_qty = qty
        self.__place_price = actual_price
        order="symbol={}&side={}&type={}&quantity={}&price={}&timeInForce=GTC".format(
            self.__pair, sell_buy, limit, qty, actual_price )
        if self.__logger is not None:
            self.__logger.warning("[{}] {}".format(self.__pair, order))
        if self._dry_run:
            result = { "orderId": "1" }
        else:
            result = rest_api("/api/v3/order", order, operation="POST" )
        if result is not None and "orderId" in result:
            if self.__logger is not None:
                self.__logger.warning("[{}] <<< {} order (id = {}) is placed at {}".format( self.__pair, sell_buy, result["orderId"], actual_price))
            order = Order(self, self.__pair, result["orderId"])
            order._qty = qty
            order._price = actual_price
            return order
        if self.__logger is not None:
            self.__logger.warning("[{}] {}".format(self.__pair, result))
            self.__logger.warning("[{}] !!! FAILED TO PLACE ORDER".format( self.__pair ))
        return None


    """
        Places sell order
    """
    def place_sell_order(self, price, quote):
        order = self._place_order("SELL", price, "LIMIT", quote)
        if order is None:
            return None
        return order


    """
        Places buy order
    """
    def place_buy_order(self, price, quote):
        order = self._place_order("BUY", price, "LIMIT", quote)
        if order is None:
            return None
        return order

    """
        Cancels all or single order
    """
    def cancel_orders(self, orderId = None):
        if self._dry_run:
            return []
        if orderId is not None:
            result = rest_api("/api/v3/order", "symbol={}&orderId={}".format(self.__pair, orderId), operation="DELETE")
        else:
            result = rest_api("/api/v3/openOrders", "symbol={}".format(self.__pair), operation="DELETE")
        return result

    """
        Returns list of current orders
    """
    def get_orders(self, orderId = None):
        if self._dry_run:
            return []
        result = rest_api("/api/v3/openOrders", "symbol={}".format(self.__pair))
        if orderId is not None:
            temp = []
            for a in result:
                if a["orderId"] == orderId:
                    temp = [a]
                    break
            result = temp
        return result

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

    def read_candles(self):
        candles = rest_api("/api/v3/klines", "symbol={}&limit=1000&interval={}".format( self.__pair, self.__minutes ), timestamp=False, signature=False )
        for c in candles[:-1]:  # Last candle is still open
            candle = strategies.ma.Candle( candle = c )
            self.eat_candle( candle )

    def request_amount(self):
        if self._dry_run:
            self.__free = self.__virtual_coin
            self.__locked = 0
            return (0, 0, 0)
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
        return (count, locked, free)

    def read_candles(self):
        candles = rest_api("/api/v3/klines", "symbol={}&limit=2&interval={}".format( self.__pair, self.__minutes ), timestamp=False, signature=False)
        if candles == None:
            return None
        return candles



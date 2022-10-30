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


from .ma import *

class MacdSignal:
    def __init__(self, graph, price, fast=8, slow=17, fast_sell=12, slow_sell=26, signal=9):
        self._graph = graph
        self._ma_fast = MA(price, fast)
        self._ma_slow = MA(price, slow)
        self._ma_fast_sell = MA(price, fast_sell)
        self._ma_slow_sell = MA(price, slow_sell)
        self._macd = MA(0,1)
        self._macd_sell = MA(0,1)
        self._signal = MA(0,9)
        self._signal_sell = MA(0,9)
        self._price = price

        self._candles = graph.get_candles()
        self._trend = ""
        self._cross_counter = -1   # number of candles since last cross

    def load_config(self, config):
        if config.has_section('macd_strategy'):
            return True

    def save_config(self, config):
        config.add_section('macd_strategy')

    def reset_boughts(self):
        return

    def sell_on_stop_loss(self):
        return True

    def _get_ma_cross(self, index, macd, signal):
        last_trend = macd.median(index - 1) - signal.median( index - 1)
        trend = macd.median(index) - signal.median( index )
        if last_trend > 0 and trend < 0:
            return "SELL"
        if last_trend < 0 and trend > 0:
            return "BUY"
        return "WAIT"

    def _get_min(self, index):
        return min( self._candles[index].open, self._candles[index-1].open, self._candles[index-2].open, self._candles[index-3].open, self._candles[index-4].open, self._candles[index-5].open, self._candles[index-6].open )

    def _check_flat(self, index):
        i = 0
        error = self._price * 0.004
        while i < 8:
            delta = self._macd.median(index - i) - self._signal.median(index - i)
            if abs(delta) > error:
                return False
            i += 1
        return True

    def take_profit_k(self):
        return 5.0
        #return self._graph.take_profit_k()

    def get_decision(self, index):
        if index == 0:
            return ("WAIT", 0, 0, 0)
        sell_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        buy_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        stop_loss =  buy_price * 0.98  # self._get_min(index)
        error = self._macd.median(index) - self._signal.median( index)
        trend = self._get_ma_cross(index, self._macd, self._signal)
        if trend == "BUY" and self._cross_counter >= 0 and self._graph.get_mode() != "selling":
            self._trend = "BUY"
            self._cross_counter = 0
            buy_allowed = True
            #if error < self._graph.price() * 0.0001:
            #    buy_allowed = False
            if self._check_flat(index):
                buy_allowed = False
            if buy_allowed:
                return ("BUY", buy_price, "{}:{}".format(stop_loss,0.98), buy_price * self.take_profit_k())
        trend = self._get_ma_cross(index, self._macd_sell, self._signal_sell)
        if trend == "SELL"  and self._graph.get_mode() != "buying":
            self._trend = "SELL"
            self._cross_counter = 0
            return ("SELL", sell_price, 0, 0)
        self._cross_counter += 1
        if self._cross_counter < 5 and self._cross_counter > 0 and self._trend == "BUY":
            buy_allowed = True
            if self._check_flat(index):
                buy_allowed = False
            #if error < self._graph.price() * 0.00005 * self._cross_counter or self._candles[index].is_black():
            #    buy_allowed = False
            if buy_allowed:
                return ("BUY", buy_price, "{}:{}".format(stop_loss,0.98), buy_price * self.take_profit_k())
        return ("WAIT", 0, 0, 0)

    def on_sell(self, success):
        return None

    def on_buy(self, success):
        return None

    def eat_candle(self, candle):
        self._ma_fast.update( candle.close )
        self._ma_slow.update( candle.close )
        self._ma_fast_sell.update( candle.close )
        self._ma_slow_sell.update( candle.close )
        self._macd.update( self._ma_fast.median(-1) - self._ma_slow.median(-1) )
        self._macd_sell.update( self._ma_fast_sell.median(-1) - self._ma_slow_sell.median(-1) )
        self._signal.update( self._macd.median(-1) )
        self._signal_sell.update( self._macd_sell.median(-1) )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        level = self._price * 0.92
        yf = [self._macd.median(index - 1)+level, self._macd.median(index)+level]
        ys = [self._signal.median(index - 1)+level, self._signal.median(index)+level]
        fig.plot(xx, ys, color="violet", linewidth = 0.3)
        fig.plot(xx, yf, color="yellow", linewidth = 0.3)
        yf = [level, level]
        fig.plot(xx, yf, color="white", linewidth = 0.2)

        level = self._price * 0.97
        yf = [self._macd_sell.median(index - 1) + level, self._macd_sell.median(index)+level]
        ys = [self._signal_sell.median(index - 1)+level, self._signal_sell.median(index)+level]
        fig.plot(xx, ys, color="violet", linewidth = 0.3)
        fig.plot(xx, yf, color="tomato", linewidth = 0.3)
        yf = [level, level]
        fig.plot(xx, yf, color="white", linewidth = 0.2)

        #yf = [self._macd.median(index - 1), self._macd.median(index)]
        #ys = [self._signal.median(index - 1), self._signal.median(index)]
        #fig.plot(xx, ys, color="violet", linewidth = 0.3)
        #fig.plot(xx, yf, color="yellow", linewidth = 0.3)

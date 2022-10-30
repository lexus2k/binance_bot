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

class MaCross:
    def __init__(self, graph, price, fast=9, slow=21, flat_checks=True):
        self._graph = graph
        self._ma_fast = MA(price, fast)
        self._ma_slow = MA(price, slow)
        self._candles = graph.get_candles()
        self._trend = ""
        self._cross_counter = -1   # number of candles since last cross
        self._price = price
        self._flat_checks = flat_checks

    def load_config(self, config):
        if config.has_section('ema_cross'):
            return True

    def save_config(self, config):
        config.add_section('ema_cross')

    def _get_ma_cross(self, index, ma_fast, ma_slow):
        last_trend = ma_fast.median(index - 1) - ma_slow.median( index - 1)
        trend = ma_fast.median(index) - ma_slow.median( index )
        if last_trend > 0 and trend < 0:
            return "SELL"
        if last_trend < 0 and trend > 0:
            return "BUY"
        return "WAIT"

    def take_profit_k(self):
        return 10.0
        return self._graph.take_profit_k()

    def reset_boughts(self):
        return

    def sell_on_stop_loss(self):
        return True

    def _get_min(self, index):
        return min( self._candles[index].open, self._candles[index-1].open, self._candles[index-2].open, self._candles[index-3].open, self._candles[index-4].open, self._candles[index-5].open, self._candles[index-6].open )

    def get_decision(self, index):
        if index == 0:
            return ("WAIT", 0, 0, 0)
        sell_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        buy_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        stop_loss =  self._get_min(index)
        error = self._ma_fast.median(index) - self._ma_slow.median( index)
        trend = self._get_ma_cross(index, self._ma_fast, self._ma_slow)
        if trend == "BUY": # and self._cross_counter > 4:
            self._trend = "BUY"
            self._cross_counter = 0
            allow_buy = True
            if self._flat_checks:
                if error < self._graph.price() * 0.0005:
                    allow_buy = False
            if allow_buy:
                return ("BUY", buy_price, stop_loss, buy_price * self.take_profit_k())
        trend = self._get_ma_cross(index, self._ma_fast, self._ma_slow)
        if trend == "SELL":
            self._trend = "SELL"
            self._cross_counter = 0
            return ("SELL", sell_price, 0, 0)
        self._cross_counter += 1
        if self._trend == "BUY":
            allow_buy = True
            if not self._flat_checks:
                allow_buy = False
            if self._flat_checks:
                if self._cross_counter >= 4:
                    allow_buy = False
                if error < self._graph.price() * 0.0002 * self._cross_counter:
                    allow_buy = False
                if not self._candles[index].is_green():
                    allow_buy = False
            if allow_buy:
                return ("BUY", buy_price, stop_loss, buy_price * self.take_profit_k())
        return ("WAIT", 0, 0, 0)

    def on_sell(self, success):
        return None

    def on_buy(self, success):
        return None

    def eat_candle(self, candle):
        self._ma_fast.update( candle.close )
        self._ma_slow.update( candle.close )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        yf = [self._ma_fast.median(index - 1), self._ma_fast.median(index)]
        ys = [self._ma_slow.median(index - 1), self._ma_slow.median(index)]
        fig.plot(xx, ys, color="violet", linewidth = 0.3)
        fig.plot(xx, yf, color="yellow", linewidth = 0.3)

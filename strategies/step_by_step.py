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
from .macross import *
import logging

class StepByStep:
    def __init__(self, graph, price, logger = None):
        self._logger = logger
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._ma =  MA(price, 12)
        self._perc = 1.0
        self._buy_price = price
        self._sell_threshold = price
        self._buy_threshold = price
        self._first_buy = 0
        self._prices = []
        self._price_trend = MA( price, 7 )
        self._tracking_price = 0
        self._tracking_direction = None
        self._cooldown_take_profit_max = 20
        self._cooldown_take_profit_counter = 0

    def load_config(self, config):
        if config.has_section('stepbystep'):
            self._perc = config.getfloat('stepbystep','perc')
            if config.has_option('stepbystep', 'last_price'):
                self._sell_threshold = config.getfloat('stepbystep','sell_threshold')
            if config.has_option('stepbystep', 'prices'):
                v = config.get('stepbystep','prices')
                self._prices = []
                for x in v.split(','):
                    self._prices.append( float(x) )
            if config.has_option('stepbystep', 'first_buy'):
                self._first_buy = config.getfloat('stepbystep', 'first_buy')

            self._sell_threshold = self._price * ( 1 + self._perc / 100 )
            self._buy_threshold = self._price * ( 1 - self._perc / 100 )
            return True
        return False

    def save_config(self, config):
        config.add_section('stepbystep')
        config.set('stepbystep', '; Be careful. 1.005 is good for 5m depth only!')
        config['stepbystep']['perc'] = str( self._perc )
        config['stepbystep']['sell_threshold'] = str( self._sell_threshold )
        config['stepbystep']['prices'] = ','.join(["{}".format(x) for x in self._prices])
        config['stepbystep']['first_buy'] = str( self._first_buy )

    def reset_boughts(self):
        return

    def take_profit_k(self):
        return 2.0

    def get_decision(self, index):
        #if index == 0:
        #    return ("WAIT", 0, 0, 0)
        current_price = self._graph.price() if index >= -1 else self._candles[index].middle
        buy_price = current_price
        sell_price = buy_price
        if index == 0:
            buy_price = current_price * 1.0005
            sell_price = current_price * 0.9995
        new_price = current_price
        old_price = self._tracking_price
        self._tracking_price = new_price

        if self._first_buy != 0:
            self._buy_price = buy_price
            self._logger.warning("=== INITIAL BUY")
            return ("FORCE_BUY", buy_price, 0, 0 )

        if current_price < self._buy_threshold:
            if new_price < old_price * 1.0001:
                return ("WAIT", 0, 0, 0)
            self._buy_price = buy_price
            self._logger.warning("=== FORCE BUY")
            return ("FORCE_BUY", buy_price, 0, 0)

        if len(self._prices) == 0:
            return ("WAIT", 0, 0, 0)

        if current_price > self._sell_threshold:
            if new_price > old_price * 0.9999:
                return ("WAIT", 0, 0, 0)
            self._sell_price = sell_price
            self._logger.warning("=== FORCE SELL")
            return ("TAKE", sell_price, 0, 0)
        return ("WAIT", 0, 0, 0)

    def sell_on_stop_loss(self):
        return False

    def on_sell(self, success):
        if success == False:
            return None
        # Always sell the lowest price ticket
        del self._prices[0]
        if len(self._prices) > 0:
            self._sell_threshold = self._prices[0] * (1 + self._perc / 100)
        self._buy_threshold = self._sell_price * (1 - self._perc / 100)
        self._logger.warning("=== ON Sell: {} [{} - {}]".format( self._buy_price, self._buy_threshold, self._sell_threshold) )
        return None

    def on_buy(self, success):
        if success == False:
            return None
        # Always buy the lowest price first
        if self._first_buy != 0:
            self._first_buy -= self._graph.trade_amount()
            if self._first_buy <= 0:
                self._first_buy = 0
            if len(self._prices) == 0:
                self._prices.insert(0, self._buy_price)
            else:
                self._prices.append( self._prices[-1] * (1 + self._perc / 100) )
        else:
            self._prices.insert(0, self._buy_price)
        self._sell_threshold = self._prices[0] * (1 + self._perc / 100)
        self._buy_threshold = self._buy_price * (1 - self._perc / 100)
        self._logger.warning("=== ON Buy: {} [{} - {}]".format( self._buy_price, self._buy_threshold, self._sell_threshold) )
        return None

    def eat_candle(self, candle):
        return None

    def draw(self, x, index, fig):
        # xx = [x-1,x]
        # ys = [self._ma.median(index - 1), self._ma.median(index)]
        # fig.plot(xx, ys, color="cyan", linewidth = 0.3)
        # self._strategy.draw(x, index, fig)
        return



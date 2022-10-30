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

class StupidTakeProfit:
    def __init__(self, graph, price, strategy):
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._strategy = strategy
        self._ma =  MA(price, 12)
        self._take_profit_k = 1.006
        self._buy_price = price
        self._price_trend = MA( price, 7 )
        self._cooldown_take_profit_max = 20
        self._cooldown_take_profit_counter = 0

    def load_config(self, config):
        if config.has_section('stupid_profit'):
            self._take_profit_k = config.getfloat('stupid_profit','profit_k')
            if config.has_option( 'stupid_profit','ma_index' ):
                self._ma.set_index( config.getint('stupid_profit','ma_index') )
            if config.has_option( 'stupid_profit','cooldown_take_profit_counter' ):
                self._cooldown_take_profit_counter = config.getint('stupid_profit','cooldown_take_profit_counter')
            if config.has_option( 'stupid_profit','cooldown_take_profit_max' ):
                self._cooldown_take_profit_max = config.getint('stupid_profit','cooldown_take_profit_max')
            return True

    def save_config(self, config):
        config.add_section('stupid_profit')
        config.set('stupid_profit', '; Be careful. 1.005 is good for 5m depth only!')
        config.set('stupid_profit', '; 1.006-1.010 is good for 15m depth')
        config.set('stupid_profit', '; Actually this value is asset specific')
        config.set('stupid_profit', '; ! Do not put it less than 1.002 because of stock exchange fee')
        config['stupid_profit']['profit_k'] = str( self._take_profit_k )
        config.set('stupid_profit', '; MA index is used to validate buy transactions')
        config.set('stupid_profit', '; the lower value - the less buy transactions are filtered')
        config.set('stupid_profit', '; Best value is between 10 and 20')
        config['stupid_profit']['ma_index'] = str( self._ma.get_index() )
        config.set('stupid_profit', '; Ones the counter reaches maximum value, the strategy is to')
        config.set('stupid_profit', '; cooldown takeprofit value making it a little bit lower: *0.997')
        config.set('stupid_profit', '; With each candle the counter increases by 1.')
        config.set('stupid_profit', '; This feature is required is last buy price unfortunately was at maxmimum, and the bot')
        config.set('stupid_profit', '; will never perform sell operation, because it bought asset at too high level,')
        config.set('stupid_profit', '; blocking forever some amount of money')
        config['stupid_profit']['cooldown_take_profit_counter'] = str( self._cooldown_take_profit_counter )
        config['stupid_profit']['cooldown_take_profit_max'] = str( self._cooldown_take_profit_max )

    def reset_boughts(self):
        return

    def take_profit_k(self):
        return self._take_profit_k

    def get_decision(self, index):
        if index == 0:
            self._price_trend.update(self._graph.price())
            return ("WAIT", 0, 0, 0)
        if index < -1:
            for i in range(7):
                self._price_trend.update( self._candles[index].middle )
        else:
            self._price_trend.update(self._graph.price())
        #decision = self._strategy.get_decision(index)
        self._cooldown_take_profit_counter += 1
        if self._cooldown_take_profit_counter > self._cooldown_take_profit_max and self._cooldown_take_profit_max > 0 and self._graph.has_something_to_sell():
            self._cooldown_take_profit_counter = 0
            self._graph._cooldown_take_profit(ignore_armed_flag = True)

        current_price = self._graph.price() if index >= -1 else self._candles[index].middle
        buy_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        time_to_buy = True
        time_to_sell = True
        if self._ma.trend(index) < 0.0001 * current_price:  # Generic trend is down
            time_to_buy = False
        if self._candles[index].height() < current_price * 0.001:  # Too small growth
            time_to_buy = False
        if self._candles[index].is_black(): # Previously the price was going down
            time_to_buy = False
        if self._price_trend.trend(index) <= 0:  # Trend is down
            time_to_buy = False

        if time_to_buy:
            return ("FORCE_BUY", buy_price, 0, buy_price * self.take_profit_k() )

        if self._graph._get_take_profit() == 0:
            time_to_sell = False
        if self._graph.price() >= (self._graph._get_take_profit() / self.take_profit_k() / (self.take_profit_k() + 0.004)):
            time_to_sell = False
        if not self._graph.has_something_to_sell():
            time_to_sell = False
        if time_to_sell:
            return ("LOSS", current_price, 0, 0)

        return ("WAIT", 0, 0, 0)



        #if decision[0] == "BUY":
        #    if delta_ma17 > self._price * 0.0001 and self._price_trend.trend(-1) >= 0:
        #        self._buy_price = decision[1]
        #        return (decision[0], decision[1], decision[2]* 1.01, decision[1] * self.take_profit_k())
        #    else:
        #        return ("WAIT", 0, 0, 0)
        #if decision[0] == "SELL":
        #    if decision[1] < self._buy_price * 1.002:
        #        return ("WAIT", 0, 0, 0)

    def sell_on_stop_loss(self):
        return False

    def on_sell(self, success):
        self._cooldown_take_profit_counter = 0
        self._strategy.on_sell()
        return None

    def on_buy(self, success):
        self._cooldown_take_profit_counter = 0
        self._strategy.on_buy()
        return None

    def eat_candle(self, candle):
        self._ma.update( candle.close )
        self._strategy.eat_candle( candle )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        ys = [self._ma.median(index - 1), self._ma.median(index)]
        fig.plot(xx, ys, color="cyan", linewidth = 0.3)
        self._strategy.draw(x, index, fig)
        return



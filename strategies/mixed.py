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

class MixedTakeProfit:
    def __init__(self, graph, price, strategy):
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._strategy = strategy
        self._ma =  MA(price, 17)
        self._take_profit_k = 1.006
        self._buy_price = price
        self._price_trend = MA( price, 5 )
        self._cooldown_take_profit_max = 20
        self._cooldown_take_profit_counter = 0

    def load_config(self, config):
        if config.has_section('mixed_profit'):
            self._take_profit_k = config.getfloat('mixed_profit','profit_k')
            if config.has_option( 'mixed_profit','ma_index' ):
                self._ma.set_index( config.getint('mixed_profit','ma_index') )
            if config.has_option( 'mixed_profit','cooldown_take_profit_counter' ):
                self._cooldown_take_profit_counter = config.getint('mixed_profit','cooldown_take_profit_counter')
            if config.has_option( 'mixed_profit','cooldown_take_profit_max' ):
                self._cooldown_take_profit_max = config.getint('mixed_profit','cooldown_take_profit_max')
            return True

    def save_config(self, config):
        config.add_section('mixed_profit')
        config.set('mixed_profit', '; Be careful. 1.005 is good for 5m depth only!')
        config.set('mixed_profit', '; 1.006-1.010 is good for 15m depth')
        config.set('mixed_profit', '; Actually this value is asset specific')
        config.set('mixed_profit', '; ! Do not put it less than 1.002 because of stock exchange fee')
        config['mixed_profit']['profit_k'] = str( self._take_profit_k )
        config.set('mixed_profit', '; MA index is used to validate buy transactions')
        config.set('mixed_profit', '; the lower value - the less buy transactions are filtered')
        config.set('mixed_profit', '; Best value is between 10 and 20')
        config['mixed_profit']['ma_index'] = str( self._ma.get_index() )
        config.set('mixed_profit', '; Ones the counter reaches maximum value, the strategy is to')
        config.set('mixed_profit', '; cooldown takeprofit value making it a little bit lower: *0.997')
        config.set('mixed_profit', '; With each candle the counter increases by 1.')
        config.set('mixed_profit', '; This feature is required is last buy price unfortunately was at maxmimum, and the bot')
        config.set('mixed_profit', '; will never perform sell operation, because it bought asset at too high level,')
        config.set('mixed_profit', '; blocking forever some amount of money')
        config['mixed_profit']['cooldown_take_profit_counter'] = str( self._cooldown_take_profit_counter )
        config['mixed_profit']['cooldown_take_profit_max'] = str( self._cooldown_take_profit_max )

    def reset_boughts(self):
        return

    def take_profit_k(self):
        return self._take_profit_k

    def get_decision(self, index):
        if index == 0:
            self._price_trend.update(self._graph.price())
            return ("WAIT", 0, 0, 0)
        decision = self._strategy.get_decision(index)

        self._cooldown_take_profit_counter += 1
        if self._cooldown_take_profit_counter > self._cooldown_take_profit_max and self._cooldown_take_profit_max > 0 and self._graph.has_something_to_sell():
            self._cooldown_take_profit_counter = 0
            self._graph._cooldown_take_profit(ignore_armed_flag = True)

        sell_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        time_to_buy = True
        time_to_sell = True

        if decision[0] != "SELL" and decision[0] != "LOSS":  # If loss command from built-in strategy
            time_to_sell = False
        #if decision[1] < self._buy_price * 1.002:            # If loss price is less than last buy_price, do not sell
        #    time_to_sell = False
        if time_to_sell:
            return ("LOSS", sell_price, 0, 0)

        if decision[0] != "BUY" and decision[0] != "FORCE_BUY":
            time_to_buy = False
        if self._ma.trend(index) < self._price * 0.0005:
            time_to_buy = False
        if self._price_trend.trend(index) < 0:
            time_to_buy = False

        if time_to_buy:
            self._buy_price = decision[1]
            return (decision[0], decision[1], decision[2]* 1.01, decision[1] * self.take_profit_k())

        return ("WAIT", 0, 0 ,0)

    def sell_on_stop_loss(self):
        return False

    def on_sell(self, success):
        if not success:
            return None
        self._cooldown_take_profit_counter = 0
        self._strategy.on_sell(success)
        return None

    def on_buy(self, success):
        if not success:
            return None
        self._cooldown_take_profit_counter = 0
        self._strategy.on_buy(success)
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


class AdvancedTakeProfit:
    def __init__(self, graph, price):
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._ma =  MA(price, 7)
        self._take_profit_k = 1.004
        self._buy_price = price
        self._just_sold = False
        self._max_candles_hold = 10
        self._ticks = self._max_candles_hold

    def load_config(self, config):
        if config.has_section('mixed_profit_adv'):
            self._take_profit_k = config.getfloat('mixed_profit_adv','profit_k')
            if config.has_option( 'mixed_profit_adv','ma_index' ):
                self._ma.set_index( config.getint('mixed_profit_adv','ma_index') )
            if config.has_option( 'mixed_profit_adv','max_candles_hold' ):
                self._max_candles_hold = config.getint('mixed_profit_adv','max_candles_hold')
            if config.has_option( 'mixed_profit_adv','ticks' ):
                self._ticks = config.getint('mixed_profit_adv','ticks')
        return True

    def save_config(self, config):
        config.add_section('mixed_profit_adv')
        config.set('mixed_profit_adv', '; Be careful. 1.004 is good for 5m depth only!')
        config.set('mixed_profit_adv', '; 1.007-1.010 is good for 15m depth')
        config.set('mixed_profit_adv', '; Actually this value is asset specific')
        config.set('mixed_profit_adv', '; ! Do not put it less than 1.002 because of stock exchange fee')
        config['mixed_profit_adv']['profit_k'] = str( self._take_profit_k )
        config.set('mixed_profit_adv', '; MA index is used to validate buy transactions')
        config.set('mixed_profit_adv', '; the lower value - the less buy transactions are filtered')
        config.set('mixed_profit_adv', '; Best value is between 10 and 20')
        config['mixed_profit_adv']['ma_index'] = str( self._ma.get_index() )
        config.set('mixed_profit_adv', '; Maximum number of candlesticks to hold asset')
        config.set('mixed_profit_adv', '; If no profit is detected, the asset will be sold on current price')
        config['mixed_profit_adv']['max_candles_hold'] = str( self._max_candles_hold )
        config.set('mixed_profit_adv', '; Current ticks for maximum number of candlesticks: from max to 1')
        config['mixed_profit_adv']['ticks'] = str( self._ticks )

    def reset_boughts(self):
        return

    def take_profit_k(self):
        return self._take_profit_k

    def get_decision(self, index):
        self._just_sold = False
        sell_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        price = self._candles[index].close
        delta_ma5 = self._ma.median(index) - self._ma.median(index - 1 )
        if delta_ma5 > self._price * 0.0001 and self._candles[index].is_green():
            return ( "FORCE_BUY", price, price * 0.999, price * self.take_profit_k() )
        if self._ticks > 0:
            self._ticks -= 1
            if self._ticks == 0 and self._graph.has_something_to_sell():
                self._ticks = -1
                return ("LOSS", sell_price, 0, 0)
        return ("WAIT", 0, 0, 0)

    def sell_on_stop_loss(self):
        return False

    def on_sell(self, success):
        if not success:
            return None
        self._just_sold = True
        self._ticks = self._max_candles_hold
        return None

    def on_buy(self, success):
        if not success:
            return None
        self._ticks = self._max_candles_hold
        return None

    def eat_candle(self, candle):
        self._ma.update( candle.close )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        ys = [self._ma.median(index - 1), self._ma.median(index)]
        fig.plot(xx, ys, color="cyan", linewidth = 0.3)
        return


class AdvancedTakeProfitExp:
    def __init__(self, graph, price):
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._ma =  MA(price, 7)
        self._take_profit_k = 1.004
        self._buy_price = price
        self._ticks = -1
        self._just_sold = False
        self._max_candles_hold = 10

    def load_config(self, config):
        if config.has_section('mixed_profit_adv'):
            self._take_profit_k = config.getfloat('mixed_profit_adv','profit_k')
            if config.has_option( 'mixed_profit_adv','ma_index' ):
                self._ma.set_index( config.getint('mixed_profit_adv','ma_index') )
            if config.has_option( 'mixed_profit_adv','max_candles_hold' ):
                self._max_candles_hold = config.getint('mixed_profit_adv','max_candles_hold')
        return True

    def save_config(self, config):
        config.add_section('mixed_profit_adv')
        config.set('mixed_profit_adv', '; Be careful. 1.004 is good for 5m depth only!')
        config.set('mixed_profit_adv', '; 1.007-1.010 is good for 15m depth')
        config.set('mixed_profit_adv', '; Actually this value is asset specific')
        config.set('mixed_profit_adv', '; ! Do not put it less than 1.002 because of stock exchange fee')
        config['mixed_profit_adv']['profit_k'] = str( self._take_profit_k )
        config.set('mixed_profit_adv', '; MA index is used to validate buy transactions')
        config.set('mixed_profit_adv', '; the lower value - the less buy transactions are filtered')
        config.set('mixed_profit_adv', '; Best value is between 10 and 20')
        config['mixed_profit_adv']['ma_index'] = str( self._ma.get_index() )
        config.set('mixed_profit_adv', '; Maximum number of candlesticks to hold asset')
        config.set('mixed_profit_adv', '; If no profit is detected, the asset will be sold on current price')
        config['mixed_profit_adv']['max_candles_hold'] = str( self._max_candles_hold )

    def take_profit_k(self):
        return self._take_profit_k

    def get_decision(self, index):
        #if index == 0 and self._just_sold:
        #    self._just_sold = False
        #    price = self._graph.price()
        #    delta_ma5 = self._ma.median(index) - self._ma.median(index - 1 )
        #    if delta_ma5 > self._price * 0.0001 and price <= self._graph.get_candle().open and self._graph.get_candle().is_green():
        #        return ( "FORCE_BUY", price, price * 0.999, price * self.take_profit_k() )

        self._just_sold = False
        if index == 0:
            delta_ma5 = self._ma.median(-1) - self._ma.median(-2)
            sell_price = (self._candles[index + 1].close if index < -1 else self._graph.price()) * 1.0000
            if delta_ma5 < self._price * 0.0001 and self._graph.has_something_to_sell():
                if self._graph._get_take_profit() != 0 and sell_price <= self._graph._get_take_profit() / self.take_profit_k() / 1.004:
                    return ("LOSS", sell_price, 0, 0)
            return ("WAIT", 0, 0, 0)
        sell_price = (self._candles[index + 1].open if index < -1 else self._graph.get_candle().open) * 1.0000
        price = self._candles[index].close
        delta_ma5 = self._ma.median(index) - self._ma.median(index - 1 )
        if delta_ma5 > self._price * 0.0001:
            return ( "FORCE_BUY", price, price * 0.999, price * self.take_profit_k() )
        if self._graph._get_take_profit() != 0 and sell_price <= self._graph._get_take_profit() / self.take_profit_k() / 1.004:
            if self._graph.has_something_to_sell():
                return ("LOSS", sell_price, 0, 0)
        return ("WAIT", 0, 0, 0)

    def reset_boughts(self):
        return

    def sell_on_stop_loss(self):
        return False

    def on_sell(self, success):
        if not success:
            return None
        self._just_sold = True
        self._ticks = self._max_candles_hold
        return None

    def on_buy(self, success):
        if not success:
            return None
        self._ticks = self._max_candles_hold
        return None

    def eat_candle(self, candle):
        self._ma.update( candle.close )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        ys = [self._ma.median(index - 1), self._ma.median(index)]
        fig.plot(xx, ys, color="cyan", linewidth = 0.3)
        return

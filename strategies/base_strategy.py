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

MODE_CRITICAL = 1
MODE_DANGER = 2
MODE_NORMAL = 3


class Buy:
    def __init__(self):
        self._loss_price = 0
        self._mode = MODE_NORMAL
        self._buy_price = 0
        self._max_price = 0
        self._sell_price = 0

    def to_string(self):
        return "{},{},{},{}".format(self._mode, self._loss_price, self._buy_price, self._max_price)

    def from_string(self, s):
        r = s.split(',')
        self._mode = int( r[0] )
        self._loss_price = float( r[1] )
        self._buy_price = float( r[2] )
        self._max_price = float( r[3] )



class Base:
    def __init__(self, graph, price, logger = None):
        self._graph = graph
        self._price = price
        self._candles = graph.get_candles()
        self._ma = MA( price, 21 )
        self._buying = True
        self._up_threshold = 80
        self._down_threshold = 40
        self._down_threshold_danger = 20
        self._down_threshold_critical = 8
        self._avg_price = 0
        self._instant_price = 0
        self._market_price = 0
        self._low_price = 0
        self._high_price = 0
        self._stop_loss = 0
        self._buy = []
        self._loss_price = 0
        self._buy_price = 0
        self._profit_price = 0
        self._cooldown_candles = 12
        self._buy_ticks = self._cooldown_candles
        self._loss_k = 0.983
        self._profit_k = 1.022
        self._back_view = 11
        self._p = MA( price, 4 )
        self._logger = logger
        self._mode = MODE_CRITICAL
        self._min_candle_size = 0

    def load_config(self, config):
        if config.has_option( 'new_vision','index' ):
            #self._ma.set_index( config.getint('new_vision','index') )
            i = 10
        if config.has_option( 'new_vision','buying' ):
            self._buying = config.getboolean('new_vision','buying')
        if config.has_option( 'new_vision', 'mode' ):
            self._mode = config.getint( 'new_vision', 'mode' )
        if config.has_option( 'new_vision', 'cooldown_candles' ):
            self._cooldown_candles = config.getint( 'new_vision', 'cooldown_candles' )
        if config.has_option( 'new_vision', 'min_candle'):
            self._min_candle_size = config.getfloat( 'new_vision', 'min_candle' )
        if config.has_option( 'new_vision', 'profit_k'):
            self._profit_k = config.getfloat( 'new_vision', 'profit_k' )
        if config.has_option( 'new_vision', 'loss_k'):
            self._loss_k = config.getfloat( 'new_vision', 'loss_k' )
        if config.has_option( 'new_vision', 'loss_price'):
            self._loss_price = config.getfloat( 'new_vision', 'loss_price' )
        if config.has_option( 'new_vision', 'buy_price'):
            self._buy_price = config.getfloat( 'new_vision', 'buy_price' )
        if config.has_option( 'new_vision', 'max_price'):
            self._profit_price = config.getfloat( 'new_vision', 'max_price' )
        if config.has_option( 'new_vision', 'price_avg_index' ):
            self._p.set_index( config.getint( 'new_vision', 'price_avg_index' ) )
        if config.has_option( 'new_vision', 'back_view' ):
            self._back_view = config.getint( 'new_vision', 'back_view' )
        self._buy = []
        i = 0
        while config.has_option( 'new_vision', 'buys{}'.format(i) ):
            buy = Buy()
            buy.from_string( config.get( 'new_vision', 'buys{}'.format(i) ) )
            self._buy.append( buy )
            i = i + 1
        if self._buying:
            self._graph.set_mode("buying")
        else:
            self._graph.set_mode("selling")
        if self._logger is not None:
            self._logger.warning("[{}] Buys loaded: {}".format( self._graph.pair(), len(self._buy)  ))
        self._buy_ticks = self._cooldown_candles
        return True

    def save_config(self, config):
        config.add_section('new_vision')
        config.set('new_vision', 'buying', str(self._buying))
        config.set('new_vision', 'mode', str(self._mode))
        config.set('new_vision', ';')
        config.set('new_vision', '; cooldown candles is number of candles to skip before next buy after buy.')
        config.set('new_vision', '; This is to prevent multiple buys on market going down.')
        config.set('new_vision', 'cooldown_candles', str(self._cooldown_candles))
        config.set('new_vision', ';')
        config.set('new_vision', '; minimum candle size in parts of 1: 0.007 is a good value')
        config.set('new_vision', '; minimum candle size will limit buy operation, 0 - no limit')
        config.set('new_vision', 'min_candle', str(self._min_candle_size))
        config.set('new_vision', ';')
        config.set('new_vision', '; Profit k is multiplier for buy price. After bought the bot will wait until price goes up to value')
        config.set('new_vision', '; buy_price * profit_k and then will try to sell assets')
        config.set('new_vision', 'profit_k', str(self._profit_k))
        config.set('new_vision', 'buy_price', str(self._buy_price))
        config.set('new_vision', 'max_price', str(self._profit_price))
        config.set('new_vision', ';')
        config.set('new_vision', '; Loss k is multiplier for buy price. After bought the bot will wait until price goes down to value')
        config.set('new_vision', '; buy_price * loss_k and then will try to sell assets to prevent much loss')
        config.set('new_vision', 'loss_k', str(self._loss_k))
        config.set('new_vision', 'loss_price', str(self._loss_price))
        config.set('new_vision', 'price_avg_index', str(self._p.get_index()))
        config.set('new_vision', 'back_view', str(self._back_view))
        for i in range(len(self._buy)):
            config.set('new_vision', 'buys{}'.format(i), self._buy[i].to_string())
        return True

    def reset_boughts(self):
        self._buy = []
        return

    def check_candles(self, index, min_size, back):
        for i in range( back ):
            if self._candles[ index - i ].height() >= min_size:
                 return True
        return False

    def __check_loss_conditions(self, index):
        if not self.has_something_to_sell():
            return None
        # Update loss threshold for the normal case, to prevent the case, when price goes up, then down,
        # we sell at lower level than buying
        if self._buy[-1]._mode == MODE_NORMAL:
            if self._instant_price > self._buy[-1]._max_price:  # If current price went above max value calculated
                self._buy[-1]._max_price = max( self._buy[-1]._max_price, self._instant_price )                         # Update max value
                st = max( self._buy[-1]._buy_price * 1.004, self._buy[-1]._max_price / ( self._profit_k*2 - 1 ) )       # Set loss pirce, so we activate loss mode only when the price went higher
                if self._buy[-1]._loss_price == 0:
                    self._buy[-1]._loss_price = st
                    if self._logger is not None:
                        self._logger.info("[{}] Price loss ARMED {}".format( self._graph.pair(), self._buy[-1]._loss_price ))
                else:
                    self._buy[-1]._loss_price = max( st, self._buy[-1]._loss_price )
                    if self._logger is not None:
                        self._logger.info("[{}] Price loss UPDATED {}".format( self._graph.pair(), self._buy[-1]._loss_price ))

        if self._buy[-1]._mode != MODE_NORMAL and self._buy[-1]._max_price != 0:
            if self._instant_price > self._buy[-1]._max_price:
                self._buy[-1]._max_price = max( self._buy[-1]._max_price, self._instant_price )
                st = max( self._buy[-1]._buy_price * 1.004, self._buy[-1]._max_price * 0.996 )
                self._buy[-1]._loss_price = max( st, self._buy[-1]._loss_price )
                if self._logger is not None:
                    self._logger.info("[{}] Price loss UPDATED {}".format( self._graph.pair(), self._buy[-1]._loss_price ))

        if self._buy[-1]._loss_price != 0 and self._buy[-1]._loss_price < self._avg_price: # Let's track loss price to prevent big loss
            self._buy[-1]._loss_price = max( self._buy[-1]._loss_price, self._avg_price * self._loss_k )

        if self._low_price < self._buy[-1]._loss_price:
            if self._logger is not None:
                self._logger.info("[{}] Price went too low: {}, Loss: {}, max_price: {}, buy_price {}".format(
                                  self._graph.pair(), self._market_price, self._buy[-1]._loss_price, self._buy[-1]._max_price, self._buy[-1]._buy_price ))
            self._buy[-1]._sell_price = self._market_price
            if self._market_price < self._buy[-1]._buy_price:
                return ("LOSS", self._market_price, 0, 0)
            else:
                return ("TAKE", self._market_price, 0, 0)
        return None

    def check_buy_conditions(self, index):
        return (True, None)

    def __check_buy_conditions(self, index):
        time_to_buy = True
        self._stop_loss = self._avg_price * self._loss_k
        self._profit_price = self._market_price * ( 1 + (self._profit_k - 1) * 1.6 )

        self._mode = MODE_NORMAL

        #if self._ma.trend( index ) < -self._p.median( index ) * 0.0001:
        #    time_to_buy = False
        buy_comment = ""
        if time_to_buy:
            ( time_to_buy, comment ) = self.check_buy_conditions( index )
            if comment is not None:
                buy_comment = comment
        if time_to_buy and not self.check_candles( index, self._instant_price * self._min_candle_size, 7 ):
            time_to_buy = False
            buy_comment = "Candles are too small"
        if time_to_buy and not self._graph.can_buy_more():
            time_to_buy = False
            buy_comment = "Cannot buy anymore, limit is reached"
        if time_to_buy and self.has_something_to_sell() and self._buy_ticks < self._cooldown_candles and self._graph.can_buy_more(): # if not sold for 2 hours+
            time_to_buy = False
            buy_comment = "Cooldown period is not finished"

        if self._logger is not None:
            self._logger.info("[{}] BUY_MODE COMMENT: {}".format( self._graph.pair(), buy_comment ))
        #print("BUY_MODE: {}".format( buy_comment ))
        if time_to_buy:
            self._buy_price = self._market_price
            self._loss_price = self._stop_loss
            return ("FORCE_BUY", self._market_price, 0, 0)
        self._buy_ticks += 1
        return None

    def check_sell_conditions(self, index):
        return (True, None)

    def __check_sell_conditions(self, index):
        if not self.has_something_to_sell():
            return None

        time_to_sell = True
        sell_comment = ""
        #if self._p.trend( index ) > 0:
        #    time_to_sell = False
        if time_to_sell and self._market_price < self._buy[-1]._buy_price * self._profit_k: # If price is too low, just wait
            time_to_sell = False
            sell_comment = "Price too low - can sell on loss only"
        #if self._buying:
        #    time_to_sell = False
        #    sell_comment = "Not selling"
        if time_to_sell:
            (time_to_sell, comment) = self.check_sell_conditions(index)
            if comment is not None:
                sell_comment = comment
        if self._logger is not None:
            self._logger.info("[{}] SELL_MODE COMMENT: {} ".format( self._graph.pair(), sell_comment ))
        if time_to_sell:
            self._buy[-1]._sell_price = self._market_price
            return ("TAKE", self._market_price, 0, 0)

        return None

    def get_decision(self, index):
        self._instant_price = self._candles[index + 1].open if  index < -1 else self._graph.price()
        if index == 0:
            self._p.update( self._instant_price )
        self._avg_price = self._candles[index + 1].open if  index < -1 else self._p.median(index)
        self._high_price = self._candles[index + 1].high if  index < -1 else self._p.median(index)
        self._low_price = self._candles[index + 1].low if  index < -1 else self._p.median(index)
        self._market_price = self._avg_price
        if self._p.trend(index) > 0:
            self._market_price = self._market_price * 1.0003
        else:
            self._market_price = self._market_price * 0.9997

        result = self.__check_loss_conditions( index )
        if result != None:
            return result

        if index == 0:
            return ("WAIT", 0, 0 ,0)

        result = self.__check_sell_conditions( index )
        if result != None:
            return result

        result = self.__check_buy_conditions( index )
        if result != None:
            return result

        return ("WAIT", 0, 0 ,0)  # LOSS, FORCE_BUY, BUY, SELL

    def sell_on_stop_loss(self):
        return True

    def has_something_to_sell(self):
        return len(self._buy) > 0

    def __push_buy(self):
        self._buy_ticks = 0
        buy = Buy()
        buy._mode = self._mode
        buy._loss_price = self._loss_price
        buy._buy_price = self._buy_price
        buy._max_price = self._profit_price
        self._buy.append( buy )

    def __pop_buy(self):
        if  self._buy[-1]._sell_price != 0 and self._buy[-1]._sell_price > self._buy[-1]._buy_price:
            self._buy_ticks = self._cooldown_candles
        else:
            self._buy_ticks = round( self._cooldown_candles / 3, 0)
        self._buy.pop()
        self._loss_price = 0
        self._buy_price = 0
        self._profit_price = 0

    def on_sell(self, success):
        if success:
            self._buying = True
            self.__pop_buy()
        return None

    def on_buy(self, success):
        if success:
            self._buying = False
            self.__push_buy()
        else:
            self._loss_price = 0
            self._buy_price = 0
            self._profit_price = 0
        return None

    def eat_candle(self, candle):
        self._ma.update( candle.close )
        self._p.update( candle.close )
        return None

    def draw(self, x, index, fig):
        xx = [x-1,x]
        ys = [ self._ma.median( index -1 ), self._ma.median( index ) ]
        fig.plot(xx, ys, color="yellow", linewidth = 0.3)
        return



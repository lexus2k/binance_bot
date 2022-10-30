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
from .base_strategy import *
import logging

class NewVision(Base):
    def __init__(self, graph, price, logger = None):
        super().__init__(graph, price, logger)
        self._rsi = RSI( 6, EMA = True )
        self._ma_rsi = RSI( 11, EMA = True )

    def load_config(self, config):
        super().load_config( config )
        if config.has_option( 'new_vision', 'rsi_low_critical' ):
            self._down_threshold_critical = config.getint( 'new_vision', 'rsi_low_critical' )
        if config.has_option( 'new_vision', 'rsi_low_danger' ):
            self._down_threshold_danger = config.getint( 'new_vision', 'rsi_low_danger' )
        if config.has_option( 'new_vision', 'rsi_low' ):
            self._down_threshold = config.getint( 'new_vision', 'rsi_low' )
        if config.has_option( 'new_vision', 'rsi_hi' ):
            self._up_threshold = config.getint( 'new_vision', 'rsi_hi' )
        if config.has_option( 'new_vision', 'use_ema_for_rsi' ):
            self._rsi.set_ema( config.getboolean( 'new_vision', 'use_ema_for_rsi' ) )
            self._ma_rsi.set_ema( config.getboolean( 'new_vision', 'use_ema_for_rsi' ) )
        self._rsi.load_config( config, 'new_vision' )


    def save_config(self, config):
        super().save_config( config )
        config.set('new_vision', '; RSI - relative strength index, - means current market state (0 - 100%)')
        config.set('new_vision', '; If rsi is below low value, it means that market is over-sold, and maybe')
        config.set('new_vision', '; the price will go up soon. If rsi is above hi value, it means that')
        config.set('new_vision', '; market is over-bought, and maybe the price will go down soon.')
        config.set('new_vision', ';')
        config.set('new_vision', '; Setting low value too small can cause, that the bot will never buy assets')
        config.set('new_vision', '; Setting low value too big can cause, that the bot will buy assets when market is flat state')
        config.set('new_vision', '; Setting hi value too big can cause, that the bot will never sell assets')
        config.set('new_vision', '; Setting hi value too small can cause, that the bot will sell assets when market in the flat state or too early')
        config.set('new_vision', 'rsi_low_critical', str(self._down_threshold_critical))
        config.set('new_vision', 'rsi_low_danger', str(self._down_threshold_danger))
        config.set('new_vision', 'rsi_low', str(self._down_threshold))
        config.set('new_vision', 'rsi_hi', str(self._up_threshold))
        config.set('new_vision', 'use_ema_for_rsi', str(self._rsi.is_ema()))
        self._rsi.save_config( config, 'new_vision' )


    def check_buy_conditions(self, index):
        time_to_buy = True
        self._stop_loss = self._avg_price * self._loss_k
        self._profit_price = self._market_price * ( 1 + (self._profit_k - 1) * 1.6 )

        self._mode = MODE_NORMAL

        #if self._ma.trend( index ) < -self._p.median( index ) * 0.0001:
        #    time_to_buy = False
        #if self._rsi.median(index) < self._ma_rsi.median( index ) - 3:
        #    time_to_buy = False
        buy_comment = None
        if time_to_buy and self._rsi.median( index ) > self._down_threshold and self._rsi.median( index - 1 ) > self._down_threshold: # self._rsi.median(index) > self._up_threshold
            time_to_buy = False
            buy_comment = "RSI {} is higher than {} down threshold".format(self._rsi.median( index ), self._down_threshold)
        if time_to_buy and self._rsi.check_low( self._down_threshold_danger, back = self._back_view, index = index ): # No boughts when values nearby are too low
            if self._logger is not None:
                self._logger.info("[{}] NV: RSI is too low < {}  (back:{})".format( self._graph.pair(), self._down_threshold_danger, self._back_view ))
            self._stop_loss = self._avg_price * ( 1 - (1 - self._loss_k) / 1.3 )
            self._profit_price = self._avg_price * self._profit_k
            buy_comment = "RSI(6) {} is lower than {} danger threshold".format(self._rsi.median( index ), self._down_threshold_danger)
            self._mode = MODE_DANGER
            # time_to_buy = False
        if time_to_buy and self._rsi.check_low( self._down_threshold_critical, back = self._back_view, index = index ): # No boughts when values nearby are too low
            if self._logger is not None:
                self._logger.info("[{}] NV: RSI(6) is too low < {}  (back:{})".format( self._graph.pair(), self._down_threshold_critical, self._back_view ))
            self._stop_loss = self._avg_price * ( 1 - (1 - self._loss_k) / 1.5 )
            self._profit_price = self._avg_price * min(1.004, self._profit_k)
            buy_comment = "RSI(6) {} is lower than {} critical threshold".format(self._rsi.median( index ), self._down_threshold_critical)
            self._mode = MODE_CRITICAL
            time_to_buy = False
        if time_to_buy and self._ma_rsi.median( index ) > self._down_threshold and self._ma_rsi.median( index - 1 ) > self._down_threshold: # self._rsi.median(index) > self._up_threshold
            time_to_buy = False
            buy_comment = "MA RSI(11) {} is higher than {} down threshold".format(self._ma_rsi.median( index ), self._down_threshold)
        if time_to_buy and self._rsi.cross( self._ma_rsi, index ) != "up":
            time_to_buy = False
            buy_comment = "no up cross"
        # if not self._buying:
        #    time_to_buy = False
        #    buy_comment = "Not buying"
        #if time_to_buy and self._ma_rsi.check_flat( threshold = 10, back = self._back_view, index = index ):
        #    time_to_buy = False
        #    buy_comment += ", Super flat"
        return ( time_to_buy, buy_comment )


    def check_sell_conditions(self, index):
        time_to_sell = True
        sell_comment = None
        #if self._p.trend( index ) > 0:
        #    time_to_sell = False
        #if self._rsi.median( index ) > self._ma_rsi.median( index ) + 3:
        #    time_to_sell = False
        if time_to_sell and self._rsi.median( index) < self._up_threshold and self._rsi.median( index - 1 ) < self._up_threshold: # or self._rsi.median( index ) < self._down_threshold:
            sell_comment = "RSI {} is lower than {} up threshold".format( self._rsi.median( index), self._up_threshold )
            time_to_sell = False
        if time_to_sell and self._rsi.cross( self._ma_rsi, index ) != "down":
            time_to_sell = False
            sell_comment = "No down cross"
        #if self._ma_rsi.median( index) < self._up_threshold and self._ma_rsi.median( index - 1 ) < self._up_threshold: # or self._rsi.median( index ) < self._down_threshold:
        #    time_to_sell = False
        #if self._buying:
        #    time_to_sell = False
        #    sell_comment = "Not selling"
        #if abs(self._rsi.median(index) - self._ma_rsi.median( index )) > 15:
        #    time_to_sell = False
        return ( time_to_sell, sell_comment )

    def get_decision(self, index):
        result = super().get_decision( index )
        if index != 0 and self._logger is not None:
            lp = 0
            bp = 0
            mp = 0
            if self.has_something_to_sell():
                lp = self._buy[-1]._loss_price
                bp = self._buy[-1]._buy_price
                mp = self._buy[-1]._max_price
            self._logger.info("[{}] NV: RSI:{}, RSI_MA:{}, AVGP:{}, PRICE:{}, LOSS:{}, BUY:{}, MAX: {}, OWN: {}".format( self._graph.pair(),
                 self._rsi.median( index ), self._ma_rsi.median(index), self._avg_price, self._instant_price, lp, bp, mp, len(self._buy)))
        return result


    def eat_candle(self, candle):
        super().eat_candle( candle )
        self._rsi.update( candle.close )
        self._ma_rsi.update( candle.close )
        return None

    def draw(self, x, index, fig):
        super().draw(x, index, fig)
        xx = [x-1,x]
        top = self._price * 0.95
        bottom = self._price * 0.9
        line80 = (top - bottom) * self._up_threshold / 100 + bottom
        line20 = (top - bottom) * self._down_threshold / 100 + bottom
        ys = [ bottom + self._rsi.median( index -1 ) / 100 * (top - bottom),
               bottom + self._rsi.median( index ) / 100 * (top - bottom) ]
        fig.plot(xx, ys, color="yellow", linewidth = 0.3)
        ys = [ bottom + self._ma_rsi.median( index -1 ) / 100 * (top - bottom),
               bottom + self._ma_rsi.median( index ) / 100 * (top - bottom) ]
        fig.plot(xx, ys, color="cyan", linewidth = 0.3)
        fig.plot(xx, [top,top], color="white", linewidth = 0.3 )
        fig.plot(xx, [line80,line80], color="red", linewidth = 0.2 )
        fig.plot(xx, [line20,line20], color="red", linewidth = 0.2 )
        fig.plot(xx, [bottom,bottom], color="white", linewidth = 0.3 )
        return

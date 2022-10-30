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


import time

def millis():
    return round(time.time() * 1000)

class Candle:
    def __init__(self, candle = None, price = None, duration = 5):
        if candle is not None:
            self.high = float(candle[2])
            self.low = float(candle[3])
            self.open = float(candle[1])
            self.middle = (self.low + self.high) / 2
            self.close = float(candle[4])
            self.open_time = int(candle[0]) / 1000
            self.close_time = int(candle[6]) / 1000
            self.duration_sec = self.close_time - self.open_time
            self.duration_min = round(self.duration_sec / 60, 0)
        if price is not None:
            self.reset(price)
            self.duration_sec = duration * 60
            self.duration_min = duration

    def update(self, price):
        self.close_time = millis() / 1000
        self.low = min( self.low, price )
        self.high = max( self.high, price )
        self.middle = (self.low + self.high) / 2
        self.count += 1
        if self.is_closed():
            self.close = price

    def height(self):
        return abs(self.open - self.close)

    def reset(self, price):
        self.sum = price
        self.high = price
        self.low = price
        self.open = price
        self.close = price
        self.count = 1
        self.open_time = millis() / 1000
        self.close_time = self.open_time
        self.middle = (self.low + self.high) / 2

    def is_closed(self):
        return self.duration_sec <= self.close_time - self.open_time

    def is_black(self):
        return self.open > self.close

    def is_green(self):
        return self.close > self.open

class MA:
    # max index in candles
    # candle duration in minutes
    def __init__(self, value, index = 5, EMA = True):
        self.__index = index
        self.__price = [value]
        self.__is_ema = EMA

    def get_index(self):
        return self.__index

    def set_index(self, index):
        self.__index = index

    def is_ema(self):
        return self.__is_ema

    def set_ema( self, ema ):
        self.__is_ema = ema

    def load_config(self, config, section):
        if config.has_option( section, "index" ):
            self.__index = config.getint( section, "index" )
        self.__price = []
        index = 0
        # Temporary disable to avoid flooding
        # while config.has_option( section, "price{}".format( index ) ):
        #    self.__price = config.getfloat( section, "price{}".format( index ) )
        #    index += 1

    def save_config(self, config, section):
        if not config.has_section( section ):
            config.add_section( section )
        config.set( section, 'index', str(self.__index))
        #for i in range( len(self.__price) ):
        #    config.set( section, 'price{}'.format( i ), str( self.__price[i] ))

    def median(self, index):
        if index == 0:
            index = -1
        if len(self.__price) < -index:
            return 0
        return self.__price[index]

    def trend(self, index):
        if index == 0:
            index = -1
        if -(index - 1) > len(self.__price):
            return 0
        return self.__price[index] - self.__price[index-1]

    def update(self, new_price):
        if len( self.__price ) == 0:
            self.__price = [new_price]
        price = self.__price[-1]
        if self.__is_ema:
            K = 2 / ( self.__index + 1 )
        else:
            K = 1 / self.__index
        price = new_price * K + price * ( 1 - K )
        self.__price.append( price )
        if len( self.__price ) > 1000:
            del self.__price[0]


class RSI:
    # max index in candles
    # candle duration in minutes
    def __init__(self, index = 5, EMA = True):
        self.__u = MA(0, index, EMA = EMA)
        self.__d = MA(0, index, EMA = EMA)
        self.__price = 0

    def get_index(self):
        return self.__u.get_index()

    def set_index(self, index):
        self.__u.set_index( index )
        self.__d.set_index( index )

    def is_ema(self):
        return self.__u.is_ema()

    def set_ema( self, ema ):
        self.__u.set_ema( ema )
        self.__d.set_ema( ema )

    def load_config(self, config, section):
        self.__u.load_config( config, section )
        self.__d.load_config( config, section )
        if config.has_option( section, "rsi_price" ):
            self.__price = config.getfloat( section, "rsi_price" )
        self.__price = 0

    def cross(self, rsi, index):
        yf1 = self.median( index - 1 )
        ys1 = rsi.median( index - 1 )
        yf2 = self.median( index )
        ys2 = rsi.median( index )
        if yf1 < ys1 and yf2 >= ys2:
            return "up"
        if yf1 > ys1 and yf2 <= ys1:
            return "down"
        return None

    def check_low(self, low, back, index):
        for i in range( back ):
            if self.median( index - i ) < low:
                return True
        return False

    def check_flat(self, threshold, back, index):
        sum = 0
        for i in range( back ):
            sum += self.median( index - i )
        avg = sum / back
        for i in range( back ):
            if abs(self.median( index - i ) - avg) > threshold:
                return False
        return True

    def save_config(self, config, section):
        if not config.has_section( section ):
            config.add_section( section )
        self.__u.save_config( config, section )
        config.set( section, "rsi_price", str(self.__price) )

    def median(self, index):
        if index == 0:
            index = -1
        u = self.__u.median(index)
        d = self.__d.median(index)
        if d == 0:
            return 100.0
        rs = u / d
        rsi = 100 - 100 / (1 + rs)
        return rsi

    def update(self, new_price):
        if self.__price == 0:
            self.__price = new_price
            return
        delta = new_price - self.__price
        if delta >= 0:
            self.__u.update( delta )
            self.__d.update( 0 )
        else:
            self.__u.update( 0 )
            self.__d.update( -delta )
        self.__price = new_price

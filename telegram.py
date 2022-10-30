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


import requests
import time

def telegram_send(msg):
    if telegram_chat_id is None or telegram_bot_token is None:
        return
    host = "https://api.telegram.org/bot" + telegram_bot_token + "/sendMessage"
    try:
        result = requests.post(host, data = {"chat_id": telegram_chat_id, "text": msg, "disable_notification": "1"})
        result = result.json()
    except:
        result = None
    # print(result)
    return result

green_emoji = u'\U0001F49A'
blue_emoji = u'\U0001F499'
red_emoji = u'\U0001F4A5'

def config_telegram(token, chat_id):
    global telegram_bot_token
    global telegram_chat_id
    telegram_chat_id = chat_id
    telegram_bot_token = token

telegram_bot_token = None
telegram_chat_id = None


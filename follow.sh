#!/bin/sh

journalctl -u asset_hot.service \
           -u asset_doge.service \
           -u asset_etc.service \
           -u asset_eth.service \
           -u asset_btt.service \
           -u asset_yfi.service \
           -u asset_btc.service \
           -u asset_ltc.service \
           -u asset_nano.service \
           -f


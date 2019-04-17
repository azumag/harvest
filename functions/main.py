# -*- coding: utf-8 -*-
import os
import sys
import time
import base64
import ccxt
import random
import uuid
import json
import logging
import urllib.request
import traceback
# import slackweb
from time import sleep
from datetime import datetime
from google.cloud import datastore
from pyti.exponential_moving_average import exponential_moving_average as ema
logger = logging.getLogger()
logger.setLevel(logging.INFO)

datastore_client = datastore.Client()

def read_environ(key, default):
    if key in os.environ:
        return os.environ[key]
    else:
        return default

# ----- CONFIGURATION -----#
API_KEY = read_environ('API_KEY', None)
SECRET = read_environ('SECRET', None)

# --- globals ----
EXCHANGER_CONST = {
    'bitbank': {
        'trading_fee': 0.0015 
    }
}

def get_ticker(exchange, symbol):
    orderbook = exchange.fetch_order_book (symbol)
    bid = orderbook['bids'][0][0] if len (orderbook['bids']) > 0 else None
    ask = orderbook['asks'][0][0] if len (orderbook['asks']) > 0 else None
    spread = (ask - bid) if (bid and ask) else None
    return ask, bid, spread

def rate_store(request):
    exchangers = ['bitbank']
    symbols = ['BTC/JPY', 'XRP/JPY', 'MONA/JPY', 'BCH/JPY']

    for exchange in exchangers:
        exchanger = eval('ccxt.'+ exchange +'()')
        for symbol in symbols:
            ticker = exchanger.fetch_ticker(symbol)
            last = ticker['last']
            ask, bid, spread = get_ticker(exchanger, symbol)

            kind = 'Rate'
            key = datastore_client.key(kind)
            rates = datastore.Entity(key=key)

            rates['exchanger'] = exchange
            rates['symbol'] = symbol
            rates['last'] = last
            rates['ask'] = ask
            rates['bid'] = bid
            rates['spread'] = spread
            rates['created_at'] = datetime.now()	

            datastore_client.put(rates)

def dongchang(event, context):
    params = json.loads(base64.b64decode(event['data']).decode('ascii'))
    try:
        logging.info(params)
        trend = check_trend_dongchang(params)
        logging.info(trend)
        params = state_transition(params, trend)
        update_state(params)
    except:
        update_state(params)
        raise

def state_transition(params, trend):
    exchanger = eval('ccxt.' + params['exchanger'] + "({ 'apiKey': API_KEY, 'secret': SECRET })")
    trading_fee = EXCHANGER_CONST[params['exchanger']]['trading_fee']

    state = params['state']
    if state == 'neutral':
        if trend == "UP":
            state = 'buy'
    elif state == 'buy':
        status = exchanger.create_order(params['symbol'], 'market', 'buy', params['payment'], 0)
        # status = wait_to_fill()
        params['order_id'] = status['id']
        state = 'wait_to_fill_buy'
    elif state == 'wait_to_fill_buy':
        order = exchanger.fetch_order(params['order_id'], params['symbol'])
        logging.info(order)
        if order['status'] == 'closed':
            state = 'bought'
            params['bought_price'] = order['cost']
            params['bought_fee'] = order['cost'] * trading_fee
    elif state == 'bought':
        if trend == 'DOWN':
            state = 'sell'
    elif state == 'sell':
        status = exchanger.create_order(params['symbol'], 'market', 'sell', params['payment'], 0)
        params['order_id'] = status['id']
        state = 'wait_to_fill_sell'
    elif state == 'wait_to_fill_sell':
        order = exchanger.fetch_order(params['order_id'], params['symbol'])
        logging.info(order)
        if order['status'] == 'closed':
            state = 'sold'
            params['sold_price'] = order['cost']
            params['sold_fee'] = order['cost'] * trading_fee
    elif state == 'sold':
        # TODO: cost fee
        # bought * 0.0015
        # sold * 0.0015
        profit = params['sold_price'] - params['bought_price']
        trading_fees = params['sold_fee'] + params['bought_fee']
        params['total_profit'] += (profit - trading_fees)
        # logging.info(bought_price, sold_price, profit, total_profit)
        # notify(uuid, 'profit', \
        #         "Profit: " + str(profit) + \
        #         "\n Total: " + str(total_profit) + \
        #         "\n Cost: " + str(total_cost) \
        #         , ["text", "pretext"])
        state = 'neutral'

    params['state'] = state
    return params 

# def get_state(strategy):
    # query = datastore_cient.query(kind='State')
    # query.add_filter('uuid', '=', uuid)
    # query.add_filter('strategy', '=', strategy)
    # return list(query.fetch(1))

def update_state(params):
    key = datastore_client.key('Individual', int(params['id']))
    indv = datastore.Entity(key=key)
    del(params['id'])
    params['life'] -= 1
    if params['life'] == 0 and params['state'] == 'bought':
        params['state'] = 'sell'
        # TODO: cancell order and commit reverse order
    if params['life'] <= 0 and (params['state'] == 'wait_to_fill_sell' or params['state'] == 'sold'):
        params['life'] = 0

    indv.update(params)
    datastore_client.put(indv)

def check_trend_dongchang(params):
    rates = get_rates(params)
    newest_rate = rates[0]
    buy_rates  = [ rate['last'] for rate in rates[1:params['period_buy']]]
    sell_rates = [ rate['last'] for rate in rates[1:params['period_sell']]]
    # logging.info(newest_rate, max(buy_rates), min(sell_rates))
    if newest_rate['last'] > max(buy_rates):
        return 'UP'
    if newest_rate['last'] < min(sell_rates):
        return 'DOWN'
    return None

def get_rates(params):
    query = datastore_client.query(kind='Rate')
    query.add_filter('exchanger', '=', params['exchanger'])
    query.add_filter('symbol', '=', params['symbol'])
    query.order = ['-created_at']
    return list(query.fetch(max([params['period_buy'], params['period_sell']])))
 

 
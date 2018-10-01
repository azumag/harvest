import os
import sys
from time import sleep

import ccxt
import slackweb

def read_environ(key, default):
    if key in os.environ:
        return os.environ[key]
    else:
        return default

def log(*args):
    if ("VERBOSE" in os.environ):
        print(str(args))

# ----- CONFIGURATION -----#
slack_url = read_environ('SLACK_URL', None)
slack = slackweb.Slack(url=slack_url)

profit_threshold = int(read_environ('PROFIT_THRESHOLD', 0))
interval = int(read_environ('INTERVAL', 10))
payment = int(read_environ('PAYMENT', 1000000))

## get exchange lists (you can specify it by using ENV)
exchanges = read_environ('LIST', 'bitbank, bitflyer, quoinex, zaif, coincheck')
exchange_list = [x.strip() for x in exchanges.split(',')]
log(exchange_list) # exchange_list = ccxt.exchanges

def find_diff(n):
    return n[4]

def get_ticker(exchange):
    orderbook = exchange.fetch_order_book ('BTC/JPY')
    bid = orderbook['bids'][0][0] if len (orderbook['bids']) > 0 else None
    ask = orderbook['asks'][0][0] if len (orderbook['asks']) > 0 else None
    spread = (ask - bid) if (bid and ask) else None
    return ask, bid, spread

def chance_notification(maxset, profit, buy_btc, trans_btc, sell_jpy):
    notify('', '*Chance!*',
     "Profit: _"+str(profit)+"_ JPY when _"+str(payment)+"_ JPY\nbuy: `"+ maxset[0] +"` _"+str(buy_btc)+"_ btc \n sell: `"+ maxset[1] + "` _"+str(sell_jpy)+"_ jpy",
     ["text", "pretext"])

def notify(title, pretext, text, mrkdwn_in):
    attachments = []
    attachment = {"title": title, "pretext": pretext, "text": text, "mrkdwn_in": mrkdwn_in}
    attachments.append(attachment)
    slack.notify(attachments=attachments, username='arb-bot', icon_emoji=":moneybag:")
    log(attachments)

def main():
    try:
        diffs = []
        for exchange_a in exchange_list:
            exchangea = eval('ccxt.' + exchange_a + '()')
            ask_a, bid_a, spread_a = get_ticker(exchangea)
            log(exchange_a, ask_a, bid_a)
            for exchange_b in exchange_list:
                if exchange_a == exchange_b:
                    continue
                exchangeb = eval('ccxt.' + exchange_b + '()')
                ask_b, bid_b, spread_b = get_ticker(exchangeb)
                log('  ', exchange_b, ask_b, bid_b, ask_b-bid_a)
                diffs.append([exchange_a, exchange_b, bid_a, ask_b, (ask_b - bid_a)])

        maxset = max(diffs, key=find_diff)
        # trade_fee_buy  = eval('ccxt.' + maxset[0] + '("btc/jpy")').fetchtradingfees.rate
        # trade_fee_sell = eval('ccxt.' + maxset[1] + '("btc/jpy")').fetchtradingfees.rate
        # trans_fee_btc  = eval('ccxt.' + maxset[0] + '("btc")').fetchfundingfees.rate
        # trans_fee_jpy  = eval('ccxt.' + maxset[1] + '("jpy")').fetchfundingfees.rate
        trade_fee_buy = 0.001
        trade_fee_sell = 0.001
        trans_fee_jpy = 540
        trans_fee_btc = 0.0005
        log("===== profit ===== ")
        log(maxset[4])
        profit, buy_btc, trans_btc, sell_jpy = calc_profit(payment, maxset[2], maxset[3], trade_fee_buy, trade_fee_sell, trans_fee_btc, trans_fee_jpy)
        log(profit)
        log("================== ")
        if profit >= profit_threshold:
            if slack_url:
                chance_notification(maxset, profit, buy_btc, trans_btc, sell_jpy)
    except:
        if slack_url:
            notify('Detail', 'ERROR RAISED', str(sys.exc_info()), ['text', 'pretext'])

def calc_profit(payment, buy_rate, sell_rate, trade_fee_buy, trade_fee_sell, trans_fee_btc, trans_fee_jpy):
    buy_btc = (payment/buy_rate) - ((payment/buy_rate) * trade_fee_buy)
    log("buy btc: " + str(buy_btc))
    trans_btc = buy_btc - trans_fee_btc
    log("trans btc: " + str(trans_btc))
    sell_jpy = (trans_btc-(trans_btc * trade_fee_sell)) * sell_rate
    log("sell_jpy: " + str(sell_jpy))

    profit = (sell_jpy-payment) - trans_fee_jpy
    return profit, buy_btc, trans_btc, sell_jpy

if slack_url:
    notify('Configurations', 'Arbitrage bot started', "Price Threshold: "+ str(profit_threshold) +"\n" + "LIST: " + ", ".join(exchange_list), ["text", "pretext"])

while True:
    main()
    sleep(interval)

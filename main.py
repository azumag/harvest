import os
import sys
from time import sleep
import ccxt
import slackweb
from pyti.exponential_moving_average import exponential_moving_average as ema

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
exchanger_name = 'bitbank'
#exchanger_name = 'bitflyer'

PAYMENT = float(read_environ('PAYMENT', 0.0001))
PERIOD = int(read_environ('PERIOD', 3))
DECISION_RATE_UP = float(read_environ('DECISION_RATE_UP', 0.0000001))
DECISION_RATE_DOWN = float(read_environ('DECISION_RATE_DOWN', 0.0000001))
API_KEY = read_environ('API_KEY', None)
SECRET = read_environ('SECRET', None)

# --- globals ----
exchanger = eval('ccxt.' + exchanger_name + "({ 'apiKey': API_KEY, 'secret': SECRET })")

rates = []
trend = None
SYMBOL = 'BTC/JPY'
status = {}
bought_status = {}
sold_status = {}

def get_ticker(exchange):
    orderbook = exchange.fetch_order_book ('BTC/JPY')
    bid = orderbook['bids'][0][0] if len (orderbook['bids']) > 0 else None
    ask = orderbook['asks'][0][0] if len (orderbook['asks']) > 0 else None
    spread = (ask - bid) if (bid and ask) else None
    return ask, bid, spread

def notify(title, pretext, text, mrkdwn_in):
    if slack_url == None:
        return
    attachments = []
    attachment = {"title": title, "pretext": pretext, "text": text, "mrkdwn_in": mrkdwn_in}
    attachments.append(attachment)
    slack.notify(attachments=attachments, username='arb-bot', icon_emoji=":moneybag:")
    log(attachments)

def main():
    global trend
    state = 'start'

    while True:
        try:
            log('====', state, '====')
            trend = check_trend()
            state = eval(state+"()")
        except:
            if slack_url:
                notify('Detail', 'ERROR RAISED', str(sys.exc_info()), ['text', 'pretext'])
            else:
                log('ERROR RAISED' + str(sys.exc_inf()))
            return 1
        sleep(1)

def start():
    return 'neutral'

def neutral():
    state = 'neutral'
    if trend == "UP":
        state = 'buy'
    return state

def buy():
    global status
    global bought_status
    state = 'buy'
    status = exchanger.create_order(SYMBOL, 'market', 'buy', PAYMENT, 0)
    log(status)
    status = wait_to_fill()
    if status:
        state = 'bought'
        notify(state, 'BotEvent', str(status), ["text", "pretext"])
        bought_status = status
    return state

def bought():
    state = 'bought'
    if trend == 'DOWN':
        state = 'sell'
    return state

def sell():
    global status
    global sold_status
    state = 'sell'
    status = exchanger.create_order(SYMBOL, 'market', 'sell', PAYMENT, 0)
    log(status)
    status = wait_to_fill()
    if status:
        state = 'sold'
        notify(state, 'BotEvent', str(status), ["text", "pretext"])
        sold_status = status
    return state

def sold():
    state = 'sold'
    bought_price = bought_status['cost']
    sold_price = bought_status['cost']
    profit = sold_price - bought_price
    notify(state, 'profit', str(profit), ["text", "pretext"])
    state = 'neutral'
    return state

def wait_to_fill():
    log('### Waiting to Fill')
    while True:
        sleep(1)
        order = exchanger.fetch_order(status['id'], SYMBOL)
        log(order)
        if order['status'] == 'closed':
            break
    print('### FILLED')
    return order

def check_trend():
    global rates
    result = [0]
    change_rate = 0
    trend = 'NONE'
    ticker = exchanger.fetch_ticker(SYMBOL)
    last = ticker['last']
    ask, bid, spread = get_ticker(exchanger)
    rates.append(last)
    if len(rates) >= PERIOD:
        result = ema(rates, PERIOD)
        change_rate = (result[-1] / result[-2])
        trend = "UP" if (1 + DECISION_RATE_UP < change_rate) else "DOWN" if (1 - DECISION_RATE_DOWN > change_rate) else "NONE"
    log(ask, last, bid, spread, result[-1], change_rate, trend)
    return trend

def show_options():
    return "PAYMENT: " + str(PAYMENT) + "\n" \
        "PERIOD: " + str(PERIOD) + "\n" \
        "DECISION_RATE_UP: " + str(DECISION_RATE_UP) + "\n" \
        "DECISION_RATE_DOWN: " + str(DECISION_RATE_DOWN) + "\n" \

if slack_url:
    notify('Configurations', 'bot started', show_options(), ["text", "pretext"])


main()

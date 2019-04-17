import os
import sys
import time
from time import sleep
import ccxt
import slackweb
from pyti.exponential_moving_average import exponential_moving_average as ema
import random
import uuid

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

PAYMENT_RANGE = int(read_environ('PAYMENT_RANGE', 100))

INSTANCE_COST = float(read_environ('INSTANCE_COST', 0.0002))
LIFE = int(read_environ('LIFE', random.gauss(8, 8)))
INTERVAL = int(read_environ('INTERVAL', random.gauss(60, 60)))
PAYMENT = float(read_environ('PAYMENT', 0.0001*random.gauss(PAYMENT_RANGE, PAYMENT_RANGE)))
PERIOD_BUY = int(read_environ('PERIOD_BUY', random.gauss(40, 40)))
PERIOD_SELL = int(read_environ('PERIOD_SELL', random.gauss(20, 20)))
API_KEY = read_environ('API_KEY', None)
SECRET = read_environ('SECRET', None)
SYMBOL = read_environ('SYMBOL', 'BTC/JPY')

sleep(INTERVAL)

# --- globals ----
exchanger = eval('ccxt.' + exchanger_name + "({ 'apiKey': API_KEY, 'secret': SECRET })")

uuid = str(uuid.uuid1()) 

buy_rates = []
sell_rates = []
trend = None
status = {}
bought_status = {}
sold_status = {}
total_profit = 0
start_time = time.time()
total_cost = 0

def show_options():
    return "`" + uuid + "`\n" \
        "TOTAL: " + str(total_profit) + "\n" \
        "SYMBOL: " + SYMBOL + "\n" \
        "PAYMENT: " + str(PAYMENT) + "\n" \
        "PERIOD_B: " + str(PERIOD_BUY) + "\n" \
        "PERIOD_S: " + str(PERIOD_SELL) + "\n" \
        "SLEEP: " + str(INTERVAL) + "\n" \
        "LIFE: " + str(LIFE) + "\n" \


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
    slack.notify(attachments=attachments, username='Harvest:dongchang', icon_emoji=":moneybag:")
    log(attachments)

def dongchang(request):
    global trend
    global total_cost
    state = 'start'

    while True:
        try:
            log('====', state, '====')
            now = time.time()
            lifetime = now - start_time
            total_cost = INSTANCE_COST * lifetime
            log("Life Time [sec]: COST", lifetime, total_cost)
            trend = check_trend()
            state = eval(state+"()")
            if check_life():
                died_clean(state)
                notify('DIED', uuid, show_options(), ['text', 'pretext']) 
                log('DIED', uuid, show_options()) 
                break
        except:
            if slack_url:
                notify(uuid, 'ERROR RAISED', str(sys.exc_info()), ['text', 'pretext'])
                notify('DIED', uuid, show_options(), ['text', 'pretext']) 
            died_clean(state)
            log('ERROR RAISED' + str(sys.exc_inf()))
            traceback.print_exc()
            return 1
        sleep(INTERVAL)

def died_clean(state):
    if state == 'bought':
        sell()
        sold()

def check_life():
    return (total_profit < 0) or (((total_profit+LIFE) - total_cost) < 0)

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
        notify(uuid, state, str(status), ["text", "pretext"])
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
        notify(uuid, state, str(status), ["text", "pretext"])
        sold_status = status
    return state

def sold():
    global total_profit
    state = 'sold'
    bought_price = bought_status['cost']
    sold_price = sold_status['cost']
    profit = sold_price - bought_price
    total_profit += profit
    log(bought_price, sold_price, profit, total_profit)
    notify(uuid, 'profit', \
            "Profit: " + str(profit) + \
            "\n Total: " + str(total_profit) + \
            "\n Cost: " + str(total_cost) \
            , ["text", "pretext"])
    state = 'neutral'
    return state

def wait_to_fill():
    log('### Waiting to Fill')
    while True:
        sleep(INTERVAL)
        order = exchanger.fetch_order(status['id'], SYMBOL)
        log(order)
        if order['status'] == 'closed':
            break
    print('### FILLED')
    return order

def check_trend():
    global buy_rates
    global sell_rates
    result = [0]
    change_rate = 0
    trend = 'NONE'
    ticker = exchanger.fetch_ticker(SYMBOL)
    last = ticker['last']
    ask, bid, spread = get_ticker(exchanger)
    if len(buy_rates) >= PERIOD_BUY:
        if last > max(buy_rates):
            trend = 'UP'
        buy_rates.pop(0)
    if len(sell_rates) >= PERIOD_SELL:
        if last < min(sell_rates):
            trend = 'DOWN'
        sell_rates.pop(0)
            
    buy_rates.append(last)
    sell_rates.append(last)
    log(ask, last, bid, spread, trend)
    return trend

if slack_url:
    notify('Configurations', 'bot started', show_options(), ["text", "pretext"])


main()

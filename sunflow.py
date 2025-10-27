### Sunflow Cryptobot ###
#
# File that drives it all! 

# Load external libraries
from pathlib import Path
import asyncio, argparse, contextlib, importlib, json, pprint, sys, time, traceback, websockets
import pandas as pd

# Load internal libraries
import database, defs, optimum, orders, preload, trailing

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run the Sunflow Cryptobot with a specified config.")
parser.add_argument('-c', '--config', default='config.py', help='Specify the config file (with .py extension).')
args = parser.parse_args()

# Resolve config file path
config_path = Path(args.config).resolve()
if not config_path.exists():
    print(f"Config file not found at {config_path}, aborting...\n")
    sys.exit()

# Dynamically load the config module
sys.path.append(str(config_path.parent))
config_module_name = config_path.stem
config = importlib.import_module(config_module_name)


### Initialize variables ###

# Debug
debug                                = config.debug                                # Debug

# Set default values
symbol                               = config.symbol                               # Symbol bot used for trading
info                                 = {}                                          # Instrument info on symbol
spot                                 = 0                                           # Spot price, always equal to lastPrice
ticker                               = {}                                          # Ticker data, including lastPrice and time
profit                               = config.profit                               # Minimum profit percentage
multiplier                           = config.multiplier                           # Multiply minimum order quantity by this
prices                               = {}                                          # Last prices based on ticker data
timestamp                            = defs.now_utc()[4]                           # Get the current time

# Minimum spread between historical buy orders
use_spread                           = {}                                          # Spread
use_spread['enabled']                = config.spread_enabled                       # Use spread as buy trigger
use_spread['distance']               = config.spread_distance                      # Minimum spread in percentages

# Technical
use_indicators                       = {}                                          # Technical indicators
use_indicators['enabled']            = config.indicators_enabled                   # Use technical indicators as buy trigger
use_indicators['minimum']            = config.indicators_minimum                   # Minimum advice value
use_indicators['maximum']            = config.indicators_maximum                   # Maximum advice value
use_indicators['klines']             = {}                                          # Klines for symbol
use_indicators['limit']              = config.indicators_limit                     # Number of klines
use_indicators['average']            = config.indicators_average                   # Calculate average of all active intervales
use_indicators['intervals']           = {}                                         # Klines intervals
use_indicators['intervals'][0]        = 0                                          # Average of all active intervals
use_indicators['intervals'][1]        = config.indicators_interval_1               # Klines timeframe interval 1
use_indicators['intervals'][2]        = config.indicators_interval_2               # Klines timeframe interval 2
use_indicators['intervals'][3]        = config.indicators_interval_3               # Klines timeframe interval 3

# Orderbook
use_orderbook                        = {}                                          # Orderbook
use_orderbook['enabled']             = config.orderbook_enabled                    # Use orderbook as buy trigger
use_orderbook['depth']               = config.orderbook_bandwith                   # Depth bandwith in percentages used to calculate market depth from orderbook
use_orderbook['window']              = config.orderbook_window                     # Rolling window orderbook data
use_orderbook['minimum']             = config.orderbook_minimum                    # Minimum orderbook buy percentage
use_orderbook['maximum']             = config.orderbook_maximum                    # Maximum orderbook buy percentage
use_orderbook['average']             = config.orderbook_average                    # Average out orderbook depth data or use last data point
use_orderbook['limit']               = config.orderbook_limit                      # Number of orderbook data elements to keep in database
use_orderbook['timeframe']           = config.orderbook_timeframe                  # Timeframe for averaging out
depth_data                           = {'time': [], 'buy_perc': [], 'sell_perc': []}

# Trade
use_trade                            = {}
use_trade['enabled']                 = config.trade_enabled                        # Use realtime trades as buy trigger
use_trade['minimum']                 = config.trade_minimum                        # Minimum trade buy ratio percentage
use_trade['maximum']                 = config.trade_maximum                        # Maximum trade buy ratio percentage
use_trade['limit']                   = config.trade_limit                          # Number of trade orders to keep in database
use_trade['timeframe']               = config.trade_timeframe                      # Timeframe in ms to collect realtime trades
trades                               = {'time': [], 'side': [], 'size': [], 'price': []}

# Optimize profit and trigger price distance
optimizer                            = {}                                          # Profit and trigger price distance optimizer
optimizer['enabled']                 = config.optimizer_enabled                    # Try to optimize the minimum profit and distance percentage
optimizer['spread_enabled']          = config.optimizer_spread                     # If optimizer is active, also optimize spread
optimizer['sides']                   = config.optimizer_sides                      # If optimizer is active, optimize both buy and sell, or only sell
optimizer['method']                  = config.optimizer_method                     # Method used to optimize distance, profit and / or spread
optimizer['profit']                  = config.profit                               # Initial profit percentage when Sunflow started, will never change
optimizer['distance']                = config.wave_distance                        # Initial trigger price distance percentage when Sunflow started, will never change
optimizer['spread']                  = config.spread_distance                      # Initial minimum spread in percentages when Sunflow started, will never change
optimizer['interval']                = config.optimizer_interval                   # Interval used for indicator KPI
optimizer['delta']                   = config.optimizer_delta                      # Delta used for indicator KPI
optimizer['limit_min']               = config.optimizer_limit_min                  # Minimum miliseconds of spot price data
optimizer['limit_max']               = config.optimizer_limit_max                  # Maximum miliseconds of spot price data
optimizer['adj_min']                 = config.optimizer_adj_min                    # Minimum adjustment
optimizer['adj_max']                 = config.optimizer_adj_max                    # Maximum adjustment
optimizer['scaler']                  = config.optimizer_scaler                     # Scales the final optimizer value by multiplying by this value
optimizer['df']                      = pd.DataFrame()                              # Dataframe is empty at start

# Price limits
use_pricelimit                       = {}                                          # Use pricelimits to prevent buy or sell
use_pricelimit['enabled']            = config.pricelimit_enabled                   # Set pricelimits functionality
use_pricelimit['max_buy_enabled']    = False                                       # Set pricelimits maximum buy price toggle  
use_pricelimit['min_sell_enabled']   = False                                       # Set pricelimits minimum sell price toggle
use_pricelimit['max_sell_enabled']   = False                                       # Set pricelimits maximum sell price toggle
use_pricelimit['min_buy']            = config.pricelimit_min_buy                   # Minimum buy price 
use_pricelimit['max_buy']            = config.pricelimit_max_buy                   # Maximum buy price 
use_pricelimit['min_sell']           = config.pricelimit_min_sell                  # Minimum sell price
use_pricelimit['max_sell']           = config.pricelimit_max_sell                  # Maximum sell price
if config.pricelimit_min_buy > 0     : use_pricelimit['min_buy_enabled'] = True    # Minimum buy price enabled
if config.pricelimit_max_buy > 0     : use_pricelimit['max_buy_enabled'] = True    # Maximum buy price enabled
if config.pricelimit_min_sell > 0    : use_pricelimit['min_sell_enabled'] = True   # Minimum sell price enabled
if config.pricelimit_max_sell > 0    : use_pricelimit['max_sell_enabled'] = True   # Maximum sell price enabled

# Trailing order
active_order                         = {}                                          # Trailing order data
active_order['side']                 = ""                                          # Trailing Buy or Sell
active_order['active']               = False                                       # Trailing order active or not
active_order['start']                = 0                                           # Start price when trailing order began     
active_order['previous']             = 0                                           # Previous price
active_order['current']              = 0                                           # Current price
active_order['created']              = 0                                           # Create timestamp in ms
active_order['updated']              = 0                                           # Update timestamp in ms
active_order['wiggle']               = config.wave_wiggle                          # Method to use to calculate trigger price distance
active_order['distance']             = config.wave_distance                        # Default trigger price distance percentage
active_order['wave']                 = config.wave_distance                        # Calculated trigger price distance percentage
active_order['fluctuation']          = config.wave_distance                        # Applied trigger price distance percentage
active_order['regime']               = ""                                          # Regime used to calculate distance when set to intelligent
active_order['orderid']              = ""                                          # Order ID
active_order['linkedid']             = ""                                          # Linked SL order ID
active_order['trigger']              = 0                                           # Trigger price for order
active_order['trigger_new']          = 0                                           # New trigger price when trailing 
active_order['trigger_ini']          = 0                                           # Initial trigger price when trailing
active_order['qty']                  = 0                                           # Order quantity
active_order['qty_new']              = 0                                           # New order quantity when trailing

# Databases for buy and sell orders
all_buys                             = {}                                          # All buys retreived from database file buy orders
all_sells                            = {}                                          # Sell order linked to database with all buys orders

# Websockets to use
ws_kline                             = False                                       # Initialize ws_kline
ws_orderbook                         = False                                       # Initialize ws_orderbook
ws_trade                             = False                                       # Initialize ws_trade
if config.indicators_enabled         : ws_kline     = True                         # Use klines websocket
if config.orderbook_enabled          : ws_orderbook = True                         # Use orderbook websocket
if config.trade_enabled              : ws_trade     = True                         # Use trade websocker

# Initialize indicators advice variable
indicators_advice    = {}
indicators_advice[0] = {'result': False, 'value': 0, 'level': 'Neutral', 'filled': False}   # Average advice of all active intervals
indicators_advice[1] = {'result': False, 'value': 0, 'level': 'Neutral', 'filled': False}   # Advice for interval 1
indicators_advice[2] = {'result': False, 'value': 0, 'level': 'Neutral', 'filled': False}   # Advice for interval 2
indicators_advice[3] = {'result': False, 'value': 0, 'level': 'Neutral', 'filled': False}   # Advice for interval 3

# Initialize orderbook advice variable
orderbook_advice                     = {}
orderbook_advice['buy_perc']         = 0
orderbook_advice['sell_perc']        = 0
orderbook_advice['result']           = False

# Initialize trade advice variable
trade_advice                         = {}
trade_advice['buy_ratio']            = 0
trade_advice['sell_ratio']           = 0
trade_advice['result']               = False

# Initialize pricelimit advice variable
pricelimit_advice                    = {}
pricelimit_advice['buy_result']      = False
pricelimit_advice['sell_result']     = False

# Compounding
compounding                          = {}
compounding['enabled']               = config.compounding_enabled
compounding['start']                 = config.compounding_start
compounding['now']                   = config.compounding_start

# Locking handle_ticker function to prevent race conditions
lock_ticker                          = {}
lock_ticker['time']                  = timestamp
lock_ticker['delay']                 = 5000
lock_ticker['enabled']               = False

# Uptime ping
uptime_ping                          = {}
uptime_ping['time']                  = timestamp
uptime_ping['record']                = timestamp
uptime_ping['delay']                 = config.uptime_delay                         # 10 seconds
uptime_ping['expire']                = config.uptime_expire                        # 1 hour
uptime_ping['enabled']               = True

# Periodic tasks
periodic                             = {}
periodic['time']                     = timestamp
periodic['delay']                    = 3600000                                     # 1 hour
periodic['enabled']                  = True

# Channel handlers
channel_handlers                     = {}


### Functions ###

# Handle messages to keep tickers up to date
def handle_ticker(message):
    
    # Debug and speed
    debug = False
    speed = False
    stime = defs.now_utc()[4]
       
    # Errors are not reported within websocket
    try:
   
        # Declare some variables global
        global spot, ticker, profit, active_order, all_buys, all_sells, prices, indicators_advice, lock_ticker, use_spread, optimizer, compounding, uptime_ping, info

        # Initialize variables
        ticker              = {}
        result              = ()
        error_code          = 0
        error_msg           = ""
        current_time        = defs.now_utc()[4]
        lock_ticker['time'] = current_time
        
        # Decode message and get the latest ticker
        ticker['time']          = int(message['data'][0]['ts'])
        ticker['lastPrice']     = float(message['data'][0]['last'])
        active_order['current'] = ticker['lastPrice']

        # Popup new price
        prices['time'].append(ticker['time'])
        prices['price'].append(ticker['lastPrice'])
        
        # Remove last price if necessary
        if current_time - prices['time'][0] > optimizer['limit_max']:
            prices['time'].pop(0)
            prices['price'].pop(0)

        # Show incoming message
        if debug:
            defs.announce(f"Debug: *** Incoming ticker with price {ticker['lastPrice']} {info['quoteCoin']} at {ticker['time']} ms ***")

        # Prevent race conditions
        if lock_ticker['enabled']:
            spot = ticker['lastPrice']
            defs.announce("Function is busy, Sunflow will catch up with next tick")
            if speed: defs.announce(defs.report_exec(stime, "function busy"))
            return
        
        # Lock handle_ticker function
        lock_ticker['enabled'] = True

        # Run trailing if active
        if active_order['active']:
            result       = trailing.trail(ticker['lastPrice'], compounding, active_order, info, all_buys, all_sells, prices)
            active_order = result[0]
            all_buys     = result[1]
            compounding  = result[2]
            info         = result[3]
        
        # Has price changed, then run all kinds of actions
        if spot != ticker['lastPrice']:

            # Store new spot price
            new_spot = ticker['lastPrice']

            # Reset uptime notice
            uptime_ping['time']   = current_time
            uptime_ping['record'] = current_time

            # Optimize profit and distance percentages
            if optimizer['enabled']:
                result       = optimum.optimize(prices, profit, active_order, use_spread, optimizer)
                profit       = result[0]
                active_order = result[1]
                use_spread   = result[2]
                optimizer    = result[3]

            # Check if and how much we can sell
            result                  = orders.check_sell(new_spot, profit, active_order, all_buys, use_pricelimit, pricelimit_advice, info)
            all_sells_new           = result[0]
            active_order['qty_new'] = result[1]
            can_sell                = result[2]
            rise_to                 = result[3]

            # Report to stdout "Price went up/down from ..."
            message = defs.report_ticker(spot, new_spot, rise_to, active_order, all_buys, info)
            defs.announce(message)
            
            # If trailing buy is already running while we can sell
            if active_order['active'] and active_order['side'] == "Buy" and can_sell:
                
                # Report to stdout
                defs.announce("*** Warning: Buying while selling is possible, trying to cancel buy order! ***")
                
                # Cancel trailing buy, remove from all_buys database
                active_order['active'] = False
                result     = orders.cancel_order(active_order['orderid'])
                response   = result[0]
                error_code = result[1]
                error_msg  = result[2]

                # Check if cancel order was OK                
                if error_code == 0:

                    # Situation normal, just remove the order
                    defs.announce("Buy order cancelled successfully")
                    all_buys = database.remove_buy(active_order['orderid'], all_buys, info)

                elif error_code == 51503:

                    # Trailing buy was bought (51503 = Your order has already been filled or canceled)
                    defs.announce("Buy order could not be cancelled, closing trailing buy")
                    result       = trailing.close_trail(active_order, all_buys, all_sells, spot, info)
                    active_order = result[0]
                    all_buys     = result[1]
                    all_sells    = result[2]
                    
                else:
                    # Something went very wrong
                    message = f"*** Error: Failed to cancel order while trailing ***\n>>> Message: {error_code} - {error_msg}"
                    defs.log_error(message)
                
            # Initiate sell
            if not active_order['active'] and can_sell:
                # There is no old quantity on first sell
                active_order['qty'] = active_order['qty_new']
                # Fill all_sells for the first time
                all_sells = all_sells_new                
                # Place the first sell order
                active_order = orders.sell(new_spot, active_order, prices, info)
              
            # Amend existing sell trailing order if required
            if active_order['active'] and active_order['side'] == "Sell":

                # Only amend order if the quantity to be sold has changed and is below threshold
                if (active_order['qty_new'] != active_order['qty']) and (active_order['qty_new'] >= info['minOrderQty']):

                    # Amend order quantity
                    result        = trailing.adjust_qty(active_order, all_buys, all_sells, all_sells_new, compounding, spot, info)
                    active_order  = result[0]
                    all_sells     = result[1]
                    all_sells_new = result[2]
                    compounding   = result[3]

            # Work as a true gridbot when only spread is used
            if use_spread['enabled'] and not use_indicators['enabled'] and not active_order['active']:
                active_order = buy_matrix(new_spot, active_order, all_buys, 1)

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        frame_summary = tb_info[-1]
        filename = frame_summary.filename
        line = frame_summary.lineno
        defs.log_error(f"*** Warning: Exception in {filename} on line {line}: {e} ***")

    # Always set new spot price and unlock function
    spot = ticker['lastPrice']
    lock_ticker['enabled'] = False
    
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Close function
    return

# Handle messages to keep klines up to date
def handle_kline(message, interval_index):

    # Debug and speed
    debug = False
    speed = False
    stime = defs.now_utc()[4]
    
    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global use_indicators, indicators_advice, active_order, all_buys

        # Initialize variables
        kline    = {}
        klines   = use_indicators['klines']
        interval = use_indicators['intervals'][interval_index]
            
        # Show incoming message
        if debug: 
            defs.announce(f"Debug: *** Incoming kline for interval {interval} ***")
            pprint.pprint(message)
            print()

        # Decode message and get the latest kline
        row = message['data'][0]
        kline['time']     =   int(row[0])
        kline['open']     = float(row[1])
        kline['high']     = float(row[2])
        kline['low']      = float(row[3])
        kline['close']    = float(row[4])
        kline['volume']   = float(row[5])
        kline['turnover'] = float(row[7])
        kline['status']   =   int(row[8])
        
        # Check if the number of klines and add in
        klines_count = len(klines[interval_index]['close'])
        if klines_count != use_indicators['limit']:
            klines[interval_index] = preload.get_klines(interval, use_indicators['limit'])
        klines[interval_index] = defs.add_kline(kline, klines[interval_index])
        defs.announce(f"Added {interval} interval onto existing {klines_count} klines")
        
        # Run buy matrix
        active_order = buy_matrix(spot, active_order, all_buys, interval_index)
        
        # Re-assign variable
        use_indicators['klines'] = klines

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        frame_summary = tb_info[-1]
        filename = frame_summary.filename
        line = frame_summary.lineno
        defs.log_error(f"*** Warning: Exception in {filename} on line {line}: {e} ***")
    
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Close function
    return

# Handle messages to keep orderbook up to date
def handle_orderbook(message):

    # Debug and speed
    debug_1 = False                        # Show orderbook
    debug_2 = False                        # Show buy and sell depth percentages
    speed   = False
    stime   = defs.now_utc()[4]
    depth   = use_orderbook['depth']
    window  = use_orderbook['window']

    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global orderbook_advice, depth_data, orderbook_levels

        # Rolling cache for last window of book levels, keyed by price per side
        if 'orderbook_levels' not in globals():
            orderbook_levels = {'bids': {}, 'asks': {}}

        # Initialize variables
        newest_timestamp        = 0
        total_buy_within_depth  = 0
        total_sell_within_depth = 0

        # Show incoming message
        if debug_1:
            defs.announce("Debug: *** Incoming orderbook ***")
            print(f"{message}\n")

        # Recalculate depth to numerical value
        depthN = ((2 * depth) / 100.0) * spot

        # Decode message and get the latest orderbook
        data_items = message.get('data', [])
        if not data_items:
            return

        # Update rolling cache with every price level from each book payload in this frame
        for book in data_items:

            # Timestamp
            timestamp = int(book.get('ts'))
            if timestamp > newest_timestamp:
                newest_timestamp = timestamp

            # Get the bids and asks
            bids = book.get('bids', [])
            asks = book.get('asks', [])

            # Update bids cache
            for lvl in bids:
                price = float(lvl[0]); size = float(lvl[1])
                orderbook_levels['bids'][price] = (size, timestamp)

            # Update asks cache
            for lvl in asks:
                price = float(lvl[0]); size = float(lvl[1])
                orderbook_levels['asks'][price] = (size, timestamp)

        # Purge anything older than window relative to newest exchange ts we saw
        if newest_timestamp == 0:
            newest_timestamp = int(time.time() * 1000)
        cutoff = newest_timestamp - window

        for side in ('bids', 'asks'):
            stale = [p for p, (_sz, ts) in orderbook_levels[side].items() if ts < cutoff]
            for p in stale:
                del orderbook_levels[side][p]

        # Buy side: (spot - depthN) .. spot
        for price, (size, _ts) in orderbook_levels['bids'].items():
            if (spot - depthN) <= price <= spot:
                total_buy_within_depth += size

        # Sell side: spot .. (spot + depthN)
        for price, (size, _ts) in orderbook_levels['asks'].items():
            if spot <= price <= (spot + depthN):
                total_sell_within_depth += size

        # Calculate total quantity (buy + sell)
        total_quantity_within_depth = total_buy_within_depth + total_sell_within_depth
        
        # Calculate percentages
        buy_percentage  = (total_buy_within_depth  / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0.0
        sell_percentage = (total_sell_within_depth / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0.0

        # Check for sanity
        if buy_percentage == 0 or sell_percentage == 0:
            defs.log_error("*** Warning: Insufficient orderbook data, increase orderbook_window in config ***")
            buy_percentage  = orderbook_advice['buy_perc']
            sell_percentage = orderbook_advice['sell_perc']

        # Output the stdout
        if debug_1:
            defs.announce(f"Debug: Orderbook rolling data")
            
            print("Orderbook")
            print("=========")
            print(f"Window            : {window} ms")
            print(f"Spot price        : {spot}")
            print(f"Window buy        : [{spot - depthN} .. {spot}]")
            print(f"Window sell       : [{spot} .. {spot + depthN}]")
            print(f"Levels cached     : {len(orderbook_levels['bids'])} bids, {len(orderbook_levels['asks'])} asks (≤ {window} ms old)\n")

            print(f"Total buy quantity : {total_buy_within_depth}")
            print(f"Total sell quantity: {total_sell_within_depth}")
            print(f"Total quantity     : {total_quantity_within_depth}\n")

            print(f"Buy within depth  : {buy_percentage:.2f} %")
            print(f"Sell within depth : {sell_percentage:.2f} %\n")

        # Announce message only if it changed and debug
        if debug_2:
            if (buy_percentage != orderbook_advice['buy_perc']) or (sell_percentage != orderbook_advice['sell_perc']):
                message = f"Debug: Orderbook information (Buy / Sell | Depth): {buy_percentage:.2f} % / {sell_percentage:.2f} % | {depth} % "
                defs.announce(message)

        # Popup new depth data
        depth_data['time'].append(defs.now_utc()[4])
        depth_data['buy_perc'].append(buy_percentage)
        depth_data['sell_perc'].append(sell_percentage)
        if len(depth_data['time']) > use_orderbook['limit']:
            depth_data['time'].pop(0)
            depth_data['buy_perc'].pop(0)
            depth_data['sell_perc'].pop(0)

        # Get average buy and sell percentage for timeframe
        new_buy_percentage  = buy_percentage
        new_sell_percentage = sell_percentage
        if use_orderbook.get('average'):
            result              = defs.average_depth(depth_data, use_orderbook, buy_percentage, sell_percentage)
            new_buy_percentage  = result[0]
            new_sell_percentage = result[1]

        # Set orderbook_advice
        orderbook_advice['buy_perc']  = new_buy_percentage
        orderbook_advice['sell_perc'] = new_sell_percentage

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        frame_summary = tb_info[-1]
        filename = frame_summary.filename
        line = frame_summary.lineno
        defs.log_error(f"*** Warning: Exception in {filename} on line {line}: {e} ***")

    # Report execution time
    if speed:
        defs.announce(defs.report_exec(stime))

    # Close function
    return

# Handle messages to keep trades up to date
def handle_trade(message):

    # To be implemented for Deribit
    
    # Debug
    debug_1 = False   # Show incoming trade
    debug_2 = False   # Show datapoints
    speed   = False
    stime   = defs.now_utc()[4]
    
    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global trade_advice, trades
        
        # Initialize variables
        result     = ()
        datapoints = {}
        compare    = {'time': [], 'side': [], 'size': [], 'price': []}

        # Show incoming message
        if debug_1: 
            defs.announce("Debug: *** Incoming trade ***")
            print(f"{message}\n")

        # Decode message and get the latest trades
        for t in message.get('data', []):
            trades['time'].append(int(t['ts']))                 # ts: exchange ms timestamp
            trades['side'].append(t['side'].capitalize())       # "buy"/"sell" -> "Buy"/"Sell"
            trades['size'].append(float(t['sz']))               # sz: trade size
            trades['price'].append(float(t['px']))              # px: trade price
                           
        # Limit number of trades
        if len(trades['time']) > use_trade['limit']:
            trades['time']  = trades['time'][-use_trade['limit']:]
            trades['side']  = trades['side'][-use_trade['limit']:]
            trades['size']  = trades['size'][-use_trade['limit']:]
            trades['price'] = trades['price'][-use_trade['limit']:]
    
        # Number of trades to use for timeframe
        number = defs.get_index_number(trades, use_trade['timeframe'], use_trade['limit'])
        compare['time']  = trades['time'][-number:]
        compare['side']  = trades['side'][-number:]
        compare['size']  = trades['size'][-number:]
        compare['price'] = trades['price'][-number:]        
    
        # Get trade_advice
        result = defs.calculate_total_values(compare)        
        trade_advice['buy_ratio']  = result[3]
        trade_advice['sell_ratio'] = result[4]
        
        # Validate data
        datapoints['trade']   = len(trades['time'])
        datapoints['compare'] = len(compare['time'])
        datapoints['limit']   = use_trade['limit']
        if (datapoints['compare'] >= datapoints['trade']) and (datapoints['trade'] >= datapoints['limit']):
            defs.log_error("*** Warning: Increase trade_limit variable in config file! ***")
        
        # Debug
        if debug_2:
            message = f"Currently {datapoints['trade']} / {datapoints['limit']} data points, "
            message = message + f"using the last {datapoints['compare']} points and "
            message = message + f"buy ratio is {trade_advice['buy_ratio']:.2f} %"
            defs.announce(message)
    
    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        frame_summary = tb_info[-1]
        filename = frame_summary.filename
        line = frame_summary.lineno
        defs.log_error(f"*** Warning: Exception in {filename} on line {line}: {e} ***")
       
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Close function
    return

# Check if we can buy the based on signals
def buy_matrix(spot, active_order, all_buys, interval_index):

    # Declare some variables global
    global indicators_advice, orderbook_advice, trade_advice, pricelimit_advice, info
    
    # Initialize variables
    can_buy       = False
    spread_advice = {}
    result        = ()
    speed         = False
    stime         = defs.now_utc()[4]
              
    # Only initiate buy and do complex calculations when not already trailing
    if not active_order['active']:
        
        # Get buy advice
        result            = defs.advice_buy(indicators_advice, orderbook_advice, trade_advice, pricelimit_advice, use_indicators, use_spread, use_orderbook, use_trade, use_pricelimit, spot, all_buys, interval_index)
        indicators_advice = result[0]
        spread_advice     = result[1]
        orderbook_advice  = result[2]
        trade_advice      = result[3]
        pricelimit_advice = result[4]
                    
        # Get buy decission and report
        result            = defs.decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, trade_advice, use_trade, pricelimit_advice, use_pricelimit, interval_index, info)
        can_buy           = result[0]
        message           = result[1]
        indicators_advice = result[2]
        defs.announce(message)

        # Determine distance of trigger price and execute buy decission
        if can_buy:
            result       = orders.buy(spot, compounding, active_order, all_buys, prices, info)
            active_order = result[0]
            all_buys     = result[1]
            info         = result[2]
    
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return active_order
    return active_order

# Prechecks to see if we can start sunflow
def prechecks():
    
    # Declare some variables global
    global symbol
    
    # Initialize variables
    goahead = True
    
    # Do checks
    if use_indicators['intervals'][3] != 0 and use_indicators['intervals'][2] == 0:
        goahead = False
        defs.announce("Interval 2 must be set if you use interval 3 for confirmation!")
        
    if not use_spread['enabled'] and not use_indicators['enabled']:
        goahead = False
        defs.announce("Need at least either Technical Indicators enabled or Spread to determine buy action!")
    
    if compounding['enabled'] and not config.balance_report:
        goahead = False
        defs.announce("When compounding set balance_report to True!")
    
    # Return result
    return goahead


### Start main program ###

## Check if we can start
if not prechecks():
    defs.announce("*** NO START ***")
    exit()


## Display welcome screen
print("\n*************************")
print("*** Sunflow Cryptobot ***")
print("*************************\n")
print(f"Symbol    : {symbol}")
if use_indicators['enabled']:
    if use_indicators['intervals'][1] != '': print(f"Interval 1: {use_indicators['intervals'][1]}")
    if use_indicators['intervals'][2] != '': print(f"Interval 2: {use_indicators['intervals'][2]}")
    if use_indicators['intervals'][3] != '': print(f"Interval 3: {use_indicators['intervals'][3]}")
if use_spread['enabled']:
    print(f"Spread    : {use_spread['distance']} %")
print(f"Profit    : {profit} %")
print(f"Prices    : {config.prices_limit}")
print(f"Timestamp : {timestamp} ms\n")


## Preload all requirements
print("\n*** Preloading ***\n")
preload.check_files()

# Preload technical indicators
if use_indicators['enabled']:
    if use_indicators['intervals'][1] != '': use_indicators['klines'][1] = preload.get_klines(use_indicators['intervals'][1], use_indicators['limit'])
    if use_indicators['intervals'][2] != '': use_indicators['klines'][2] = preload.get_klines(use_indicators['intervals'][2], use_indicators['limit'])
    if use_indicators['intervals'][3] != '': use_indicators['klines'][3] = preload.get_klines(use_indicators['intervals'][3], use_indicators['limit'])

# Preload basic price data
ticker               = preload.get_ticker()
spot                 = ticker['lastPrice']
info                 = preload.get_info(spot, multiplier, compounding)
all_buys             = database.load(config.dbase_file, info)
all_buys             = preload.check_orders(all_buys, info)
prices               = preload.get_prices(config.prices_interval, config.prices_limit)

# Preload optimizer and load prices
if optimizer['enabled']:

    # Get historical prices and combine with current prices
    prices_old   = preload.get_prices(optimizer['interval'], optimizer['prices'])
    prices       = preload.combine_prices(prices_old, prices)
    
    # Calulcate optimized data
    result       = optimum.optimize(prices, profit, active_order, use_spread, optimizer)
    profit       = result[0]
    active_order = result[1]
    use_spread   = result[2]
    optimizer    = result[3]

# Preload database inconsistencies
if config.database_rebalance:
    all_buys = orders.rebalance(all_buys, info)

# Preload balances
if config.balance_report:
    balances           = orders.report_balances(spot, all_buys, info)
    compounding['now'] = balances[0]

# Preload compounding
if compounding['enabled']:
    info = defs.calc_compounding(info, spot, compounding)

# Check funds
if config.equity_check:
    orders.check_buy(info)

## TESTS ##
print("\n*** Preloading report ***")

print("\n** Ticker **")
print(f"Symbol    : {ticker['symbol']}")
print(f"Last price: {ticker['lastPrice']} {info['quoteCoin']}")
print(f"Updated   : {ticker['time']} ms")

print("\n** Spot **")
print(f"Spot price: {spot} {info['quoteCoin']}")

print("\n** Info **")
print("Instrument information:")
pprint.pprint(info)
#print("\n** Klines **")
#pprint.pprint(klines)

if config.balance_report:
    print("\n** Value **")
    print(f"Total bot value : {balances[0]} {info['quoteCoin']}")
    print(f"Quote (exchange): {balances[2]} {info['quoteCoin']}")
    print(f"Base (exchange) : {balances[1]} {info['baseCoin']}")
    print(f"Base (database) : {balances[3]} {info['baseCoin']}")
    print(f"Out of sync     : {balances[4]} {info['baseCoin']}")

## Announce start
print("\n*** Starting ***\n")
if config.timeutc_std:
    time_output = defs.now_utc()[0] + " UTC time"
else:
    time_output = defs.now_utc()[5] + " " + config.timezone_str + " time"
defs.announce(f"Sunflow started at {time_output}")


### Periodic tasks ###

# Run tasks periodically
def periodic_tasks(current_time):

    # Debug
    debug = False

    # Declare some variables global
    global info

    # Get info
    info = preload.get_info(spot, multiplier, compounding)

    # Return
    return

# Ping message periodically
def ping_message(current_time):

    # Debug
    debug = False

    # Initialize variables
    expire        = uptime_ping["expire"]
    delay_ping    = current_time - uptime_ping["time"]
    delay_tickers = current_time - uptime_ping["record"]

    # Check for too little action -> now force a resubscribe
    if delay_tickers > expire:

        # Reset uptime notice
        uptime_ping['time']   = current_time
        uptime_ping['record'] = current_time

        # Report to stdout
        message = f"*** Warning: Ping, last ticker update of {delay_tickers:,} ms ago is larger than {expire:,} ms maximum! ***"
        defs.log_error(message)

        # Request resubscribe
        message = f"Ticker stall: Last update {delay_tickers:,} ms > {expire:,} ms"
        request_resubscribe(message)

    # Report to stdout
    if uptime_ping["enabled"]:
        if delay_ping == delay_tickers:
            defs.announce(f"Ping, {delay_ping:,} ms since last message and ticker")
        else:
            defs.announce(f"Ping, {delay_ping:,} ms since last message and ticker update was {delay_tickers:,} ms ago")

    # Return
    return


### Websockets ###

# Load websocket
from okx.websocket.WsPublicAsync import WsPublicAsync

# Global resubscribe event and helper state container
resubmit_event = asyncio.Event()
_state = {"runners": [], "tasks": []}

# Announce once and signal the watcher to rebuild streams
def request_resubscribe(reason: str = ""):
    # Report to stdout
    if reason:
        defs.announce(f"*** Warning: Websocket resubscribe: {reason} ***")
    else:
        defs.announce("*** Warning: Websocket resubscribe ***")

    # Resubmit event set
    resubmit_event.set()

    # Return
    return

# Initialize candles
candles = {}
if use_indicators["enabled"]:
    if use_indicators["intervals"][1] != "":
        candles["candle" + use_indicators["intervals"][1]] = True
    if use_indicators["intervals"][2] != "":
        candles["candle" + use_indicators["intervals"][2]] = True
    if use_indicators["intervals"][3] != "":
        candles["candle" + use_indicators["intervals"][3]] = True

# Public callbacks
def on_message_public(raw):
    message = json.loads(raw)
    if message.get("event") in {"subscribe", "error"}:
        defs.announce(message)
        return
    if message.get("op") == "pong":
        return

    # Ticker and Orderbook
    ch = message.get("arg", {}).get("channel")
    if ch == "tickers":
        handle_ticker(message)
    elif ch in {"books", "books5", "bbo-tbt"}:
        handle_orderbook(message)

# Keyed callbacks
def on_message_business(raw):
    message = json.loads(raw)
    if message.get("event") in {"subscribe", "error"}:
        defs.announce(message)
        return
    if message.get("op") == "pong":
        return

    # Klines and Trades
    ch = message.get("arg", {}).get("channel")
    if ch and ch.startswith("candle"):
        interval = ch.replace("candle", "", 1)
        if interval == use_indicators["intervals"][1]:
            handle_kline(message, 1)
        if interval == use_indicators["intervals"][2]:
            handle_kline(message, 2)
        if interval == use_indicators["intervals"][3]:
            handle_kline(message, 3)
    elif ch == "trades-all":
        handle_trade(message)


# Runner
class Runner:
    def __init__(self, url, subs, callback):
        self.url = url
        self.subs = subs
        self.callback = callback
        self.stop_event = asyncio.Event()

    def stop(self):
        self.stop_event.set()

    async def run_once(self):
        ws = WsPublicAsync(self.url)
        try:
            await ws.start()
            await ws.subscribe(self.subs, self.callback)
            await self.stop_event.wait()
        except Exception as e:
            defs.announce(f"[{self.url}] run_once crashed: {e}")
            raise
        finally:
            # Always try to clean up
            with contextlib.suppress(Exception):
                await ws.unsubscribe(self.subs, self.callback)
            with contextlib.suppress(Exception):
                await ws.factory.close()

    async def run_forever(self):
        backoff = 1
        while not self.stop_event.is_set():
            try:
                await self.run_once()
            except Exception as e:
                defs.announce(f"[{self.url}] Disconnected: {e}. Reconnecting in {backoff}s…")
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 30)
            else:
                backoff = 1


# Helper to build runner list from current settings
def build_runners():
    runners = []

    # Public WS (channels tickers + orderbook)
    subs_public = []
    subs_public.append({"channel": "tickers", "instId": symbol})
    if use_orderbook["enabled"]:
        subs_public.append({"channel": config.api_ch_orderbook, "instId": symbol})
    if subs_public:
        runners.append(Runner(config.api_ws_public, subs_public, on_message_public))

    # Business WS (channels candles + trades-all)
    subs_business = []
    for ch, enabled in candles.items():
        if enabled:
            subs_business.append({"channel": ch, "instId": symbol})
    if use_trade["enabled"]:
        subs_business.append({"channel": "trades-all", "instId": symbol})
    if subs_business:
        runners.append(Runner(config.api_ws_business, subs_business, on_message_business))

    return runners


# Robust asyncio error handling & task logging
def _log_task_result(task: asyncio.Task):

    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        defs.log_error(f"*** Warning: Task crashed: {e} ***\n>>> Traceback: \n{tb}")
        if isinstance(e, websockets.exceptions.ConnectionClosedError):
            request_resubscribe("Runner task crashed with ConnectionClosedError")

def _loop_exception_handler(loop, context):

    msg = context.get("message", "Unhandled exception in event loop")
    exc = context.get("exception")
    task = context.get("task") or context.get("future")

    parts = [f"*** Warning: {msg} ***"]
    if task:
        try:
            tname = task.get_name()
        except Exception:
            tname = repr(task)
        parts.append(f"task={tname}")

    if exc:
        if isinstance(exc, websockets.exceptions.ConnectionClosedError):
            parts.append("exception=ConnectionClosedError (no close frame received or sent)")

            # Trigger automatic resubscribe on connection close
            request_resubscribe("Loop handler caught ConnectionClosedError")

        else:
            parts.append(f"exception={exc.__class__.__name__}: {exc}")

        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # *** CHECK *** Do not report the full traceback for now        
        # parts.append("Traceback:\n" + tb)

    defs.log_error("\n>>> Message: ".join(parts))


# Watchdog to stop when something goes wrong
async def _watch_halt(state, poll_ms=200):
    while not defs.halt_sunflow:
        await asyncio.sleep(poll_ms / 1000.0)
    # On halt, stop whatever runners are current
    for r in list(state["runners"]):
        r.stop()

# Watcher that handles resubscribe cycles
async def _watch_resubscribe(state):
    while not getattr(defs, "halt_sunflow", False):
        await resubmit_event.wait()
        resubmit_event.clear()

        # Stop existing runners
        for r in list(state["runners"]):
            r.stop()

        # Give them a moment to unwind
        await asyncio.sleep(0.1)

        # Cancel old tasks
        for t in list(state["tasks"]):
            if not t.done():
                t.cancel()
        state["tasks"].clear()

        # Rebuild runners and tasks from live config
        new_runners = build_runners()
        if not new_runners:
            defs.log_error("*** Error: Resubscribe attempted, but no streams enabled. Check settings. ***")
            continue

        state["runners"].clear()
        state["runners"].extend(new_runners)

        new_tasks = [asyncio.create_task(r.run_forever(), name=f"runner-{i}") for i, r in enumerate(new_runners)]
        for t in new_tasks:
            t.add_done_callback(_log_task_result)

        state["tasks"].extend(new_tasks)

        # Report to stdout
        defs.announce("*** Websocket streams resubscribed ***")


# Run tasks on a periodic basis
async def _housekeeping_loop(poll_ms=200):
    while not getattr(defs, "halt_sunflow", False):
        current_time = defs.now_utc()[4]

        # Uptime ping
        if current_time - uptime_ping["time"] > uptime_ping["delay"]:
            ping_message(current_time)
            uptime_ping["time"] = current_time

        # Periodic tasks
        if periodic.get("enabled") and (
            current_time - periodic["time"] > periodic["delay"]
        ):
            periodic_tasks(current_time)
            periodic["time"] = current_time

        await asyncio.sleep(poll_ms / 1000.0)


### Main ###
async def main():

    # Loop exception handler
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_loop_exception_handler)

    # Build initial runners
    runners = build_runners()
    if not runners:
        raise RuntimeError("No streams enabled. Turn on at least one in settings.")

    # Create tasks for runners
    tasks = [asyncio.create_task(r.run_forever(), name=f"runner-{i}") for i, r in enumerate(runners)]
    for t in tasks:
        t.add_done_callback(_log_task_result)

    # Seed global state for watchers
    _state["runners"] = runners
    _state["tasks"] = tasks

    # Start halt watchdog
    halt_task = asyncio.create_task(_watch_halt(_state), name="watch-halt")
    halt_task.add_done_callback(_log_task_result)

    # Start resubscribe watcher
    resub_task = asyncio.create_task(_watch_resubscribe(_state), name="watch-resub")
    resub_task.add_done_callback(_log_task_result)

    # Start housekeeping
    hk_task = asyncio.create_task(_housekeeping_loop(), name="housekeeping")
    hk_task.add_done_callback(_log_task_result)

    try:
        await asyncio.gather(*(tasks + [halt_task, resub_task, hk_task]))
    except KeyboardInterrupt:
        for r in _state["runners"]:
            r.stop()
        await asyncio.sleep(0.1)
    finally:
        for t in list(_state["tasks"]):
            if not t.done():
                t.cancel()
        for t in (halt_task, resub_task, hk_task):
            if not t.done():
                t.cancel()


### Start ###
if __name__ == "__main__":
    asyncio.run(main())

### Say goodbye ###
if config.timeutc_std:
    time_output = defs.now_utc()[0] + " UTC time"
else:
    time_output = defs.now_utc()[5] + " " + config.timezone_str + " time"
defs.announce(f"*** Sunflow terminated at {time_output} ***")

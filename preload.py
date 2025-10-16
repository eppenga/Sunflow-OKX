### Sunflow Cryptobot ###
#
# Preload ticker, klines, instrument info and other data

# Load external libraries
from loader import load_config
import os, pprint

# Load internal libraries
import database, decode, defs, exchange, orders

# Load config
config = load_config()

# Preload ticker
def get_ticker():

    # Debug
    debug = False
    
    # Initialize variables
    ticker     = {}
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Load ticker
    result     = exchange.get_ticker()
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code !=0:
        message = f"*** Error: Failed to get ticker ***\n>>> Message {error_code} - {error_msg}"
        defs.log_error(message)

    # Decode ticker
    ticker = decode.ticker(response)
    
    # Report to stdout
    defs.announce(f"Initial ticker price set to {ticker['lastPrice']} {ticker['symbol']} via exchange")

    # Debug to stdout
    if debug:
        defs.announce("Debug: Sunflow ticker data:")
        pprint.pprint(ticker)
        print()   
           
    # Return ticker
    return ticker

# Preload klines
def get_klines(interval, limit):
   
    # Debug
    debug = False
    
    # Initialize variables
    klines     = {}
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""   

    # Load klines
    result     = exchange.get_klines(interval, limit)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code !=0:
        message = f"*** Error: Failed to get klines ***\n>>> Message {error_code} - {error_msg}"
        defs.log_error(message)
      
    # Decode klines
    klines = decode.klines(response)
    
    # Check response from exchange
    amount_klines = len(klines['time'])
    if amount_klines != limit:
        message = f"*** Error: Tried to load {limit} klines, but exchange only provided {amount_klines} ***"
        defs.log_error(message)
      
    # Report to stdout
    defs.announce(f"Initial {limit} klines with {interval} interval loaded from exchange")
    
    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Prefilled klines with interval {interval}m")
        defs.announce(f"Debug: Time    : {klines['time']}")
        defs.announce(f"Debug: Open    : {klines['open']}")
        defs.announce(f"Debug: High    : {klines['high']}")
        defs.announce(f"Debug: Low     : {klines['low']}")
        defs.announce(f"Debug: Close   : {klines['close']}")
        defs.announce(f"Debug: Volume  : {klines['volume']}")
        defs.announce(f"Debug: Turnover: {klines['turnover']}")
        defs.announce(f"Debug: Status  : {klines['status']}")
    
    # return klines
    return klines

# Preload prices
def get_prices(interval, limit):

    # Debug
    debug = False
       
    # Initialize variables
    prices = {'time': [], 'price': []}

    # Get kline with the lowest interval (1 minute)
    kline_prices = get_klines(interval, limit)
    prices       = {
        'time' : kline_prices['time'],
        'price': kline_prices['close']
    }

    # Report to stdout
    defs.announce(f"Initial {limit} prices with {interval} interval extracted from klines")

    # Return prices
    return prices

# Combine two lists of prices
def combine_prices(prices_1, prices_2):
    
    # Combine and sort by 'time'
    prices = sorted(zip(prices_1['time'] + prices_2['time'], prices_1['price'] + prices_2['price']))

    # Use a dictionary to remove duplicates, keeping the first occurrence of each 'time'
    unique_prices = {}
    for t, p in prices:
        if t not in unique_prices:
            unique_prices[t] = p

    # Separate into 'time' and 'price' lists
    combined_prices = {
        'time': list(unique_prices.keys()),
        'price': list(unique_prices.values())
    }
    
    # Return combined list
    return combined_prices

# Calculations required for info
def calc_info(info, spot, multiplier, compounding):

    # Debug
    debug = False
    
    # Initialize variables
    adjusted          = 0
    add_up            = 1.1
    compounding_ratio = 1.0
    minimumQty        = info['minOrderQty'] * add_up
    
    # Do compounding if enabled
    if compounding['enabled']:
        
        # Only compound if when profitable
        if compounding['now'] > compounding['start']:
            compounding_ratio = compounding['now'] / compounding['start']

    # Round correctly, adjust for multiplier and compounding
    adjusted = minimumQty * multiplier * compounding_ratio
    info['buyBase']  = defs.round_number(adjusted, info['basePrecision'], "up")
    info['buyQuote'] = defs.round_number(adjusted * spot, info['basePrecision'], "up")
    
    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Minimum order in base is {info['buyBase']} {info['baseCoin']}")

    # Return instrument info
    return info

# Preload instrument info
def get_info(spot, multiplier, compounding):

    # Debug
    debug = False
    
    # Initialize variables
    info       = {}
    instrument = {}
    rates      = {}
    result     = ()
    error_code = 0
    error_msg  = ""  

    # Load instrument info
    result     = exchange.get_instruments()
    instrument = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code !=0:
        message = f"*** Error: Failed to get info ***\n>>> Message {error_code} - {error_msg}"
        defs.log_error(message)

    # Load fee rates
    result     = exchange.get_fees()
    rates      = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code !=0:
        message = f"*** Error: Failed to get fee rates ***\n>>> Message {error_code} - {error_msg}"
        defs.log_error(message)
   
    # Decode instrument info and fee rates
    info = decode.info(instrument)
    info = decode.fees(info, rates)

    # Calculate info['buyBase'] and info['buyQuote']
    info = calc_info(info, spot, multiplier, compounding)
       
    # Debug to stdout
    if debug:
        defs.announce("Debug: Instrument info")
        pprint.pprint(info)
        print()
  
    # Return instrument info
    return info
    
# Create empty files for check_files
def create_file(create_file, content=""):
        
    # Does the file exist and if not create a file    
    if not os.path.exists(create_file):
        with open(create_file, 'a') as file:
            if content:
                file.write(content)
            else:
                pass

    # Return
    return

# Check if necessary files exists
def check_files():
        
    # Does the data folder exist
    if not os.path.exists(config.data_folder):
        os.makedirs(config.data_folder)
    
    # Headers for files
    revenue_header = "UTCTime,createdTime,orderid,linkedid,side,symbol,baseCoin,quoteCoin,orderType,orderStatus,avgPrice,qty,triggerStart,triggerEnd,cumExecFeeCcy,cumExecFee,cumExecQty,cumExecValue,revenue\n"
    
    # Does the buy orders database exist
    create_file(config.dbase_file)                      # Buy orders database
    create_file(config.error_file)                      # Errors log file
    create_file(config.exchange_file)                   # Exchange log file
    create_file(config.revenue_file, revenue_header)    # Revenue log file
    
    defs.announce("All folders and files checked")
    
# Check if an order is valid when filled
def filled_valid(order):
    
    # Debug
    debug = False

    # Initialize variables
    valid = True
    
    # Checks
    if order['orderStatus'] != "Effective": valid = False
    if order['avgPrice'] == 0             : valid = False
    if order['cumExecFee'] == 0           : valid = False
    if order['cumExecFeeCcy'] == ""       : valid = False
    if order['cumExecQty'] == 0           : valid = False
    if order['linkedid'] == ""            : valid = False

    # Return status
    return valid
    

# Check orders in database if they still exist
def check_orders(all_buys, info):
    
    # Debug
    debug = False
    
    # Initialize variables
    message      = ""
    all_buys_new = []
    order        = {}
    temp_order   = {}
    result       = ()
    error_code   = 0
    error_msg    = ""
    quick        = config.quick_check

    # Report to stdout
    defs.announce("Checking all orders on exchange")

    # Loop through all buys
    for order in all_buys:

        # Fast check
        if quick:

            # Only check order on exchange if status is not Closed
            message = f"Checking order {order['orderid']} in database"
            defs.announce(message)

            # Check order
            temp_order = order
            if order['status'] != "Closed":
                defs.announce("Performing an additional check on order status via exchange")
                result     = orders.get_order(order['orderid'], True)
                temp_order = result[0]
                error_code = result[1]
                error_msg  = result[2]
                if error_code != 0:
                    temp_order = order
                    temp_order['orderStatus'] = "Erased"
                    message = f"*** Warning: Failed to get order! ***\n>>> Message: {error_code} - {error_msg}"
                    defs.log_error(message)

        # Slow check
        else:

            # Check all order on exchange regardless of status
            message = f"Checking order {order['orderid']} at exchange"
            defs.announce(message)
            
            # Check order
            result     = orders.get_order(order['orderid'])
            temp_order = result[0]
            error_code = result[1]
            error_msg  = result[2]
            if error_code != 0:
                temp_order = order
                temp_order['orderStatus'] = "Erased"
                message = f"*** Warning: Failed to get order! ***\n>>> Message: {error_code} - {error_msg}"
                defs.log_error(message)

        # Assign status, if not filled (effective at OKX) just disregard
        if filled_valid(temp_order):
            temp_order['status'] = "Closed"
            all_buys_new.append(temp_order)
        else:
            message = f"*** Warning: Order {temp_order['orderid']} not valid, removed from database ***"
            defs.announce(message)
    
    # Save refreshed database
    database.save(all_buys_new, info)
    
    # Return correct database
    return all_buys_new 

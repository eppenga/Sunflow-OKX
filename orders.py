### Sunflow Cryptobot ###
#
# Order functions

# Load external libraries
from loader import load_config
import pprint, requests

# Load internal libraries
import database, defs, exchange, distance, preload

# Load config
config = load_config()

# Get order details
def get_order(orderid):
    
    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
        
    # Initialize variables
    order      = {}
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Get response from exchange
    result     = exchange.get_order(orderid)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Decode response to order
    if error_code == 0:
        order = decode_order(response)
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Order details via exchange")
        pprint.pprint(response)
        print()
        defs.announce("Debug: Order details decoded")
        pprint.pprint(order)
        print()

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return order
    return order, error_code, error_msg

# Get order details
def get_linked_order(linkedid):
    
    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
        
    # Initialize variables
    fills      = {}
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Get response from exchange
    result     = exchange.get_linked_order(linkedid)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Decode response to order
    if error_code == 0:
        fills = decode_linked_order(response)
  
    # Debug to stdout
    if debug:
        defs.announce("Debug: Linked order details via exchange")
        pprint.pprint(response)
        print()
        defs.announce("Debug: Linked order details decoded")
        pprint.pprint(fills)
        print()

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return order
    return fills, error_code, error_msg

# Cancel an order at the exchange
def cancel_order(orderid):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Report to stdout
    defs.announce(f"Trying to cancel order {orderid}")
    
    # Initialize variables
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""
   
    # Cancel order at exchange, we only need the error code if any
    result     = exchange.cancel_order(orderid)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
           
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return error code
    return response, error_code, error_msg

# Decode order from exchange
def decode_order(response):
    
    # Debug
    debug = False
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Before decode:")
        pprint.pprint(response)
        print()

    # Initialize variables
    order  = {}
    result = response['data'][0]

    # Map order to response
    order['createdTime']   = int(result['cTime'])                           # Creation timestamp in ms
    order['updatedTime']   = int(result['uTime'])                           # Last update timestamp in ms
    order['orderid']       = result['algoId']                               # Order ID by exchange
    order['linkedid']      = result['ordId']                                # Linked SL order ID
    order['symbol']        = result['instId']                               # Symbol
    order['side']          = result['side'].capitalize()                    # Buy or Sell
    order['orderType']     = result['ordType'].capitalize()                 # Order type: Market, Limit, etc...
    order['orderStatus']   = result['state'].capitalize()                   # Order state: Live, Pause, Partially_effective, Effective, Canceled, Order_failed, Partially_failed
    order['price']         = float(result.get('last'))                      # Last price available in quote (USDT)
    order['qty']           = float(result.get('sz'))                        # Quantity in base (BTC)
    order['triggerPrice']  = float(result.get('slTriggerPx'))               # Trigger price in quote (USDT)
    order['avgPrice']      = 0                                              # Average fill price in quote (USDT)
    order['cumExecQty']    = 0                                              # Cumulative executed quantity in base (BTC)
    order['cumExecValue']  = 0                                              # Cumulative executed value in quote (USDT)
    order['cumExecFee']    = 0                                              # Cumulative executed fee in base for buy (BTC) and quote for sell (USDT)
    order['cumExecFeeCcy'] = ''                                             # Cumulative executed fee currency 

    # Debug to stdout
    if debug:
        defs.announce("Debug: After decode:")
        pprint.pprint(order)
        print()

    # Return order
    return order

# Decode linked order from exchange to get the fills
def decode_linked_order(response):
    
    # Debug
    debug = False
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Before decode:")
        pprint.pprint(response)
        print()

    # Initialize variables
    fills  = {}
    result = response['data'][0]

    # Map fills to response
    fills['orderStatus']   = result['state'].capitalize()                   # Order state: Canceled, Live, Partially_filled, Filled and Mmp_canceled
    fills['avgPrice']      = float(result['fillPx'])                        # Average fill price in quote (USDT)
    fills['cumExecQty']    = float(result['fillSz'])                        # Cumulative executed quantity in base (BTC)
    fills['cumExecValue']  = fills['avgPrice'] * fills['cumExecQty']        # Cumulative executed value in quote (USDT)
    fills['cumExecFee']    = float(result['fee']) * -1                      # Cumulative executed fee in base for buy (BTC) and quote for sell (USDT)
    fills['cumExecFeeCcy'] = result['feeCcy']                               # Cumulative executed fee currency 

    # Debug to stdout
    if debug:
        defs.announce("Debug: After decode:")
        pprint.pprint(fills)
        print()

    # Return fills
    return fills

# Decode fills from exchange
def decode_fills(response):
    
    # Debug
    debug = False
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Before decode:")
        pprint.pprint(response)
        print()

    # Initialize variables
    fills  = {}
    result = response['data'][0]

    # Map fills to response
    fills['avgPrice']      = float(result['fillPx'])                        # Average fill price in quote (USDT)
    fills['cumExecQty']    = float(result['fillSz'])                        # Cumulative executed quantity in base (BTC)
    fills['cumExecValue']  = fills['avgPrice'] * fills['cumExecQty']        # Cumulative executed value in quote (USDT)
    fills['cumExecFee']    = float(result['fee']) * -1                      # Cumulative executed fee in base for buy (BTC) and quote for sell (USDT)
    fills['cumExecFeeCcy'] = result['feeCcy']                               # Cumulative executed fee currency 

    # Debug to stdout
    if debug:
        defs.announce("Debug: After decode:")
        pprint.pprint(fills)
        print()

    # Return fills
    return fills

# Merge order and fills
def merge_order_fills(order, fills, info):

    # Debug
    debug = False
    
    # Merge fills into order
    order['avgPrice']      = fills['avgPrice']
    order['cumExecQty']    = defs.round_number(fills['cumExecQty'], info['basePrecision'], "down")
    order['cumExecValue']  = defs.round_number(fills['cumExecValue'], info['quotePrecision'], "down")   
    order['cumExecFee']    = fills['cumExecFee']
    order['cumExecFeeCcy'] = fills['cumExecFeeCcy']
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Merged order:")
        pprint.pprint(order)
        print()

    # Return
    return order    

# Initialize active order for initial buy or sell
def set_trigger(spot, active_order, info):

    # Debug
    defs.announce(f"Trigger price distance {active_order['fluctuation']:.4f} % and price {defs.format_number(spot, info['tickSize'])} {info['quoteCoin']}")

    # Set quantity at OKX we can always trade in base
    active_order['qty'] = info['buyBase']
    
    # Check side
    if active_order['side'] == "Buy":
        active_order['trigger'] = defs.round_number(spot * (1 + (active_order['fluctuation'] / 100)), info['tickSize'], "up")
    elif active_order['side'] == "Sell":
        active_order['trigger'] = defs.round_number(spot * (1 - (active_order['fluctuation'] / 100)), info['tickSize'], "down")
        
    # Set initial trigger price so we can remember
    active_order['trigger_ini'] = active_order['trigger']

    # Return active_order
    return active_order

# Check if we can sell based on price limit
def sell_matrix(spot, use_pricelimit, pricelimit_advice, info):
    
    # Initialize variables
    message = ""
    pricelimit_advice['sell_result'] = True
    
    # Check sell price for price limits
    if use_pricelimit['enabled']:
        
        # Check minimum sell price for price limit
        if use_pricelimit['min_sell_enabled']:
            if spot > use_pricelimit['min_sell']:
                pricelimit_advice['sell_result'] = True
            else:
                pricelimit_advice['sell_result'] = False
                message = f"price {spot} {info['quoteCoin']} is lower than minimum sell price "
                message = message + f"{defs.format_number(use_pricelimit['min_sell'], info['tickSize'])} {info['quoteCoin']}"

        # Check maximum sell price for price limit
        if use_pricelimit['max_sell_enabled']:
            if spot < use_pricelimit['max_sell']:
                pricelimit_advice['sell_result'] = True
            else:
                pricelimit_advice['sell_result'] = False
                message = f"price {spot} {info['quoteCoin']} is higher than maximum sell price "
                message = message + f"{defs.format_number(use_pricelimit['max_sell'], info['tickSize'])} {info['quoteCoin']}"

    # Return modified price limit
    return pricelimit_advice, message    

# What orders and how much can we sell with profit
def check_sell(spot, profit, active_order, all_buys, use_pricelimit, pricelimit_advice, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    qty       = 0
    counter   = 0
    message   = ""
    rise_to   = ""
    nearest   = []
    distance  = active_order['distance']
    pre_sell  = False
    can_sell  = False
    all_sells = []
    result    = ()
    
    # Check sell price limit
    result            = sell_matrix(spot, use_pricelimit, pricelimit_advice, info)
    pricelimit_advice = result[0]
    message           = result[1]
    
    # Walk through all_buys database and find profitable orders
    for order in all_buys:

        # Only walk through closed buy orders
        if order['status'] == 'Closed':
                    
            # Check if a a buy order is profitable
            profitable_price = order['avgPrice'] * (1 + ((profit + distance) / 100))
            nearest.append(profitable_price - spot)
            if spot >= profitable_price:
                qty = qty + order['cumExecQty']
                all_sells.append(order)
                counter = counter + 1
    
    # Adjust quantity to exchange regulations
    qty = defs.round_number(qty, info['basePrecision'], "down")
    
    # Do we have order to sell
    if all_sells and qty > 0:
        pre_sell = True

    # We have orders to sell, and sell price limit is not blocking 
    if pre_sell and pricelimit_advice['sell_result']:
        can_sell = True
        defs.announce(f"Trying to sell {counter} orders for a total of {defs.format_number(qty, info['basePrecision'])} {info['baseCoin']}")
    else:
        if nearest:
            rise_to = f"{defs.format_number(min(nearest), info['tickSize'])} {info['quoteCoin']}"

    # We have orders to sell, but sell price limit is blocking
    if pre_sell and not pricelimit_advice['sell_result']:
        message = f"We could sell {counter} orders, but " + message
        defs.announce(message)        

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return data
    return all_sells, qty, can_sell, rise_to
        
# New buy order
def buy(spot, compounding, active_order, all_buys, prices, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    order      = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Report to stdout
    defs.announce("*** BUY BUY BUY! ***")

    # Recalculate minimum values
    info = preload.calc_info(info, spot, config.multiplier, compounding)

    # Initialize active_order
    active_order['side']     = "Buy"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
    active_order['orderid']  = ""
    
    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price and quantity
    active_order = set_trigger(spot, active_order, info)  

    # Place buy order
    result     = exchange.place_order(active_order)
    order      = result[0]
    error_code = result[1]
    error_msg  = result[2]

    # Check if buy error was successsful
    if error_code != 0:

        # Reset active_order
        active_order['active'] = False
        
        # Report error
        message = f"*** Warning: Buy order failed when placing, trailing stopped! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)

        # Return
        if speed: defs.announce(defs.report_exec(stime))    
        return active_order, all_buys, info

    # Get order ID
    active_order['orderid'] = int(order['data'][0]['algoId'])

    # Get order details from order we just placed
    result     = get_order(active_order['orderid'])
    order      = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Check if the order we just placed was fine
    if error_code !=0:
        
        # Reset active_order
        active_order['active'] = False
        
        # Report error
        message = f"*** Warning: Failed to get buy order {active_order['orderid']} immediately after placing ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
        
        # Return
        if speed: defs.announce(defs.report_exec(stime))    
        return active_order, all_buys, info

    # Add the Sunflow status of the order
    order['status'] = "Open"

    # Debug
    if debug:
        defs.announce("Debug: Buy order details")
        pprint.pprint(order)
        print()

    # Report to stdout
    message = f"Buy order {active_order['orderid']} opened for {defs.format_number(active_order['qty'], info['basePrecision'])} {info['baseCoin']} "
    message = message + f"at trigger price {defs.format_number(active_order['trigger'], info['tickSize'])} {info['quoteCoin']}"
    defs.announce(message)

    # Store the order in the database buys file
    all_buys = database.register_buy(order, all_buys, info)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return trailing order and new buy order database
    return active_order, all_buys, info
    
# New sell order
def sell(spot, active_order, prices, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    order      = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Report to stdout
    defs.announce("*** SELL SELL SELL! ***")

    # Initialize active_order
    active_order['side']     = "Sell"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
    active_order['orderid']  = ""
  
    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price
    active_order = set_trigger(spot, active_order, info)

    # Place sell order
    result     = exchange.place_order(active_order)
    order      = result[0] 
    error_code = result[1]
    error_msg  = result[2]

    # Check if sell order was successful
    if error_code !=0:
        
        # Reset active_order
        active_order['active'] = False

        # Report error
        message = f"*** Warning: Buy order failed when placing, trailing stopped! ****\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)

        # Return
        if speed: defs.announce(defs.report_exec(stime))        
        return active_order
   
    # Get order ID
    active_order['orderid'] = int(order['data'][0]['algoId'])

    # Get order details
    result     = get_order(active_order['orderid'])
    order      = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Check if the order we just placed was fine
    if error_code !=0:
        
        # Reset active_order
        active_order['active'] = False
        
        # Report error
        message = f"*** Warning: Failed to get buy order {active_order['orderid']} immediately after placing ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
        
        # Return
        if speed: defs.announce(defs.report_exec(stime))    
        return active_order   
    
    # Debug
    if debug:
        defs.announce("Debug: Sell order details")
        pprint.pprint(order)
        print()
    
    # Report to stdout
    message = f"Sell order {active_order['orderid']} opened for {defs.format_number(active_order['qty'], info['basePrecision'])} {info['baseCoin']} "
    message = message + f"at trigger price {defs.format_number(active_order['trigger'], info['tickSize'])} {info['quoteCoin']}"
    defs.announce(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
   
    # Return data
    return active_order

# Get balance
def get_balance(currency):

    # Debug
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    balance    = 0
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""
    
    # Get response from exchange
    result     = exchange.get_balance(currency)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance for {currency}! ***"
        defs.log_error(message)
        return balance, error_code, error_msg
       
    # Decode response to balance
    try:
        details = response.get("data", [])[0].get("details", [])
        if details and "eq" in details[0]:
            balance = float(details[0].get("eq") or 0)
    except (IndexError, ValueError, TypeError):
        pass

    # Debug to stdout
    if debug:
        defs.announce("Debug: Balance information:")
        pprint.pprint(balance)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return balance
    return balance, error_code, error_msg

# Rebalances the database vs exchange by removing orders with the highest price
def rebalance(all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    equity_balance = 0
    equity_dbase   = 0
    equity_diff    = 0
    equity_remind  = 0
    equity_lost    = 0
    dbase_changed  = False
    result         = ()
    error_code     = 0
    error_msg      = ""

    # Debug to stdout
    if debug:
        defs.announce("Debug: Trying to rebalance buys database with exchange data")
   
    # Get equity for basecoin
    result         = get_balance(info['baseCoin'])
    equity_balance = result[0]
    error_code     = result[1]
    error_msg      = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
  
    # Get equity from all buys for basecoin
    equity_dbase  = float(sum(order['cumExecQty'] for order in all_buys))
    equity_remind = float(equity_dbase)
    equity_diff   = equity_balance - equity_dbase

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Before: Rebalance equity on exchange: {equity_balance} {info['baseCoin']}")
        defs.announce(f"Debug: Before: Rebalance equity in database: {equity_dbase} {info['baseCoin']}")
        defs.announce(f"Debug: Before: Exchange equity including margin: {equity_balance * (1 + (config.rebalance_margin / 100))}")

    # Selling more than we have
    while equity_dbase > equity_balance * (1 + (config.rebalance_margin / 100)):
        
        # Database changed
        dbase_changed = True
        
        # Find the item with the highest avgPrice
        highest_avg_price_item = max(all_buys, key=lambda x: x['avgPrice'])

        # Remove this item from the list
        if debug: defs.announce(f"Debug: Going to remove order {highest_avg_price_item['orderid']} from all_buys database")
        exit()
        all_buys = database.remove_buy(highest_avg_price_item['orderid'], all_buys, info)
        
        # Recalculate all buys
        equity_dbase = sum(order['cumExecQty'] for order in all_buys)    

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: After: Rebalance equity on exchange: {equity_balance} {info['baseCoin']}")
        defs.announce(f"Debug: After: Rebalance equity in database: {equity_dbase} {info['baseCoin']}")

    # Save new database
    if dbase_changed:
        equity_lost = equity_remind - equity_dbase
        defs.announce(f"Rebalanced buys database with exchange data and lost {defs.format_number(equity_lost, info['basePrecision'])} {info['baseCoin']}")
        database.save(all_buys, info)
    
    # Report to stdout
    defs.announce(f"Difference between exchange and database is {defs.format_number(equity_diff, info['basePrecision'])} {info['baseCoin']}")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return all buys
    return all_buys

# Report balances info to stdout
def report_balances(spot, all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    message_1  = ""
    message_2  = ""
    result     = ()
    error_code = 0
    error_msg  = ""

    # Get order count and quantity
    result        = database.order_count(all_buys, info)
    base_database = result[1]
      
    # Get balance for base currency
    result        = get_balance(info['baseCoin'])
    base_exchange = result[0]
    error_code    = result[1]
    error_msg     = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance for base currency! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
    
    # Get balance for quote currency
    result         = get_balance(info['quoteCoin'])
    quote_exchange = result[0]
    error_code     = result[1]
    error_msg      = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance for quote currency! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
   
    # Calculate values
    bot  = base_exchange * spot + quote_exchange    # Bot value in quote according to exchange
    lost = base_exchange - base_database            # Lost due to inconsistancies

    # Round values
    bot            = defs.round_number(bot, info['quotePrecision'], "down")
    lost           = defs.round_number(lost, info['basePrecision'], "down")
    base_exchange  = defs.round_number(base_exchange, info['basePrecision'], "down")
    base_database  = defs.round_number(base_database, info['basePrecision'], "down")
    quote_exchange = defs.round_number(quote_exchange, info['quotePrecision'], "down")
    
    # Create messsage
    message_1 = f"Bot value is {defs.format_number(bot, info['quotePrecision'])} {info['quoteCoin']} "
    message_1 = message_1 + f"({defs.format_number(base_exchange, info['basePrecision'])} {info['baseCoin']} / {defs.format_number(quote_exchange, info['quotePrecision'])} {info['quoteCoin']})"    
    message_2 = f"Database has {defs.format_number(base_database, info['basePrecision'])} {info['baseCoin']} and "
    message_2 = message_2 + f"{defs.format_number(lost, info['basePrecision'])} {info['baseCoin']} is out of sync"
          
    # Report to stdout
    defs.announce(message_1)
    defs.announce(message_2)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
 
    # Return total equity and quote
    return bot, base_exchange, quote_exchange, base_database, lost

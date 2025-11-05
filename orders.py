### Sunflow Cryptobot ###
#
# Order functions

# Load external libraries
from loader import load_config
import pprint, requests

# Load internal libraries
import database, decode, defs, exchange, distance, preload

# Load config
config = load_config()

# Create virtual order in case exchange is not providing
def virtual_order(active_order, info):

    # Debug
    debug = False
    
    # Initialize variables
    order = {}
      
    # Set order
    order['avgPrice']     = active_order['current']
    order['createdTime']  = active_order['created']
    order['linkedid']     = "-1"
    order['orderid']      = active_order['orderid']
    order['orderStatus']  = "Effective"
    order['orderType']    = "Conditional"
    order['qty']          = active_order['qty']
    order['side']         = active_order['side']
    order['status']       = "Closed"
    order['symbol']       = info['symbol']
    order['triggerPrice'] = active_order['trigger']
    order['updatedTime']  = defs.now_utc()[4]
                 
    # Set cumulative quantity and value
    order['cumExecQty']   = order['qty']
    order['cumExecValue'] = order['qty'] * order['avgPrice']
    order['cumExecValue'] = defs.round_number(order['cumExecValue'], info['quotePrecision'], "down")
    
    # Set cumulative fees
    if active_order['side'] == "Buy":
        order['cumExecFeeCcy'] = info['baseCoin']
        order['cumExecFee']    = order['cumExecQty'] * info['feeTaker']
        order['cumExecFee']    = defs.round_number(order['cumExecFee'], info['basePrecision'], "down")
        
    elif active_order['side'] == "Sell":
        order['cumExecFeeCcy'] = info['quoteCoin']
        order['cumExecFee']    = order['cumExecValue'] * info['feeTaker']
        order['cumExecFee']    = defs.round_number(order['cumExecFee'], info['quotePrecision'], "down")
   
    # Report to stdout
    message = f"*** Warning: Created virtual order {active_order['orderid']} ! ***"
    defs.announce(message)
    
    if debug:
        defs.announce(f"Debug: Order {active_order['orderid']} fill data was set manually")
        print("active_order")
        pprint.pprint(active_order)
        print("\norder")
        pprint.pprint(order)
        print()
        
    # Return virtual created order
    return order

# Get order details
def get_order(orderid, skip=False):
    
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
    result     = exchange.get_order(orderid, skip)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Decode order
    if error_code == 0:
        order = decode.order(response)
    
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
    
    # Decode linked order to get fills
    if error_code == 0:
        fills = decode.linked_order(response)
  
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

# Merge order and fills
def merge_order_fills(order, fills, info):

    # Debug
    debug = False
    
    # Merge fills into order
    order['avgPrice']      = fills['avgPrice']
    order['cumExecQty']    = fills['cumExecQty']
    order['cumExecValue']  = fills['cumExecValue']
    order['cumExecFee']    = fills['cumExecFee']
    order['cumExecFeeCcy'] = fills['cumExecFeeCcy']
    
    # Round numbers
    order['cumExecQty']    = defs.round_number(fills['cumExecQty'], info['basePrecision'], "down")
    order['cumExecValue']  = defs.round_number(fills['cumExecValue'], info['quotePrecision'], "down")
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Merged order:")
        pprint.pprint(order)
        print()

    # Return
    return order    

# Initialize active order for initial buy or sell
def set_trigger(spot, active_order, info):

    # Report to stdout
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
        
# Do we need to buy to pay fees
def check_buy_fees(info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    result     = ()
    error_code = 0
    error_msg  = ""
    required   = info['buyBase'] * 0.5
    
    # Report to stdout
    defs.announce(f"Checking if we have enough funds for fees")
    
    # Get balances
    result     = get_balance(info['baseCoin'])
    balances   = result[0]
    error_code = result[1]
    error_msg  = result[2]
   
    # Debug
    if debug:
        print(f"Base assets equity    = {balances['equity']} {info['baseCoin']}")
        print(f"Base assets available = {balances['available']} {info['baseCoin']}")
        print(f"Required for fees     = {required} {info['baseCoin']}\n")
        
    # Check if we have at least the minimum buy
    if balances['available'] < (required):
        
        # Report to stdout
        message = f"Going to buy {required} {info['baseCoin']} for fees"
        defs.announce(message)
        
        # Buy minimum
        result = exchange.place_market_order(info['buyBase'])
        response   = result[0]
        error_code = result[1]
        error_msg  = result[2]

        # Check if buy error was successful
        if error_code !=0:
            
            # Report error
            message = f"*** Warning: Buy for fees failed ****\n>>> Message: {error_code} - {error_msg}"
            defs.log_error(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return
    return

# Do we have enough funds to buy
def check_buy(info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    result     = ()
    error_code = 0
    error_msg  = ""
    required   = info['buyQuote'] * config.equity_multiplier
    required   = defs.round_number(required, info['quotePrecision'])

    # Report to stdout
    defs.announce(f"Checking if we have enough funds to buy")

    # Get balances
    result     = get_balance(info['quoteCoin'])
    balances   = result[0]
    error_code = result[1]
    error_msg  = result[2]
       
    # Debug
    if debug:
        print(f"Quote assets equity    = {balances['equity']} {info['quoteCoin']}")
        print(f"Quote assets available = {balances['available']} {info['quoteCoin']}")        
        print(f"Required for trading   = {required} {info['quoteCoin']}\n")

    # Check if we have enough to buy
    if required > balances['equity']:
        message = f"*** Error: You need to have more than {required} {info['quoteCoin']} free to trade! ***"
        defs.log_error(message)
        
    # Check if we need to buy the smallest amount for fees
    if config.equity_for_fees:
        check_buy_fees(info)
    
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return
    return

# New buy order
def buy(spot, compounding, active_order, all_buys, prices, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    response   = {}
    order      = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Report to stdout
    defs.announce("*** BUY BUY BUY! ***")

    # Recalculate minimum values
    info = preload.calc_info(info, spot, config.multiplier, compounding)

    # Initialize active_order
    active_order['side']        = "Buy"
    active_order['active']      = True
    active_order['start']       = spot
    active_order['previous']    = spot
    active_order['current']     = spot
    active_order['created']     = defs.now_utc()[4]
    active_order['orderid']     = ""
    active_order['fluctuation'] = active_order['distance']
    active_order['last']        = active_order['distance']
    
    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price and quantity
    active_order = set_trigger(spot, active_order, info)
    
    # Check for enough equity
    if config.equity_check: check_buy(info)

    # Place buy order
    result     = exchange.place_order(active_order)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]

    # Check if buy error was successful
    if error_code !=0:
        
        # Reset active_order
        active_order['active'] = False

        # Report error
        message = f"*** Warning: Buy order failed when placing, trailing stopped! ****\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)

        # Return
        if speed: defs.announce(defs.report_exec(stime))        
        return active_order, all_buys, info

    # Decode order ID
    active_order['orderid'] = decode.orderid(response)

    # Get order details from order we just placed
    result     = get_order(active_order['orderid'])
    order      = result[0]
    error_code = result[1]
    error_msg  = result[2]

    # Order does not exist, assume it was filled
    if error_code == 51603:
        pass
   
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
    active_order['side']        = "Sell"
    active_order['active']      = True
    active_order['start']       = spot
    active_order['previous']    = spot
    active_order['current']     = spot
    active_order['created']     = defs.now_utc()[4]
    active_order['orderid']     = ""
    active_order['fluctuation'] = active_order['distance']
    active_order['last']        = active_order['distance']

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
        message = f"*** Warning: Sell order failed when placing, trailing stopped! ****\n>>> Message: {error_code} - {error_msg}"
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
    
    # Order does not exist, assume it was filled
    if error_code == 51603:
        pass

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
    balances   = {}
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
       
    # Decode balance
    balances = decode.balance(response)
       
    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Balance information:")
        pprint.pprint(balances)
        print()

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return balance
    return balances, error_code, error_msg

# Rebalances the database vs exchange by removing orders with the highest price
def rebalance(all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    equity_exchange = 0
    equity_database = 0
    equity_diff     = 0
    equity_remember = 0
    equity_lost     = 0
    dbase_changed   = False
    result          = ()
    error_code      = 0
    error_msg       = ""

    # Debug to stdout
    if debug:
        defs.announce("Debug: Trying to rebalance buys database with exchange data")
   
    # Get equity for basecoin
    result          = get_balance(info['baseCoin'])
    equity_exchange = result[0]['equity']
    error_code      = result[1]
    error_msg       = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
  
    # Get equity from all buys for basecoin
    equity_database = float(sum(order['cumExecQty'] for order in all_buys))
    equity_remember = float(equity_database)
    equity_diff     = equity_exchange - equity_database

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Before: Rebalance equity on exchange: {equity_exchange} {info['baseCoin']}")
        defs.announce(f"Debug: Before: Rebalance equity in database: {equity_database} {info['baseCoin']}")
        defs.announce(f"Debug: Before: Exchange equity including margin: {equity_exchange + (info['buyBase'] * (config.rebalance_margin / 100))}")

    # Selling more than we have
    while equity_database > equity_exchange + (info['buyBase'] * (config.rebalance_margin / 100)):
        
        # Database changed
        dbase_changed = True
        
        # Find the item with the highest avgPrice
        highest_avg_price_item = max(all_buys, key=lambda x: x['avgPrice'])

        # Remove this item from the list
        if debug: defs.announce(f"Debug: Going to remove order {highest_avg_price_item['orderid']} from all_buys database")
        all_buys = database.remove_buy(highest_avg_price_item['orderid'], all_buys, info)
        
        # Recalculate all buys
        equity_database = sum(order['cumExecQty'] for order in all_buys)    

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: After: Rebalance equity on exchange: {equity_exchange} {info['baseCoin']}")
        defs.announce(f"Debug: After: Rebalance equity in database: {equity_database} {info['baseCoin']}")

    # Save new database
    if dbase_changed:
        equity_lost = equity_remember - equity_database
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
    base_exchange = result[0]['equity']
    error_code    = result[1]
    error_msg     = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get balance for base currency! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
    
    # Get balance for quote currency
    result         = get_balance(info['quoteCoin'])
    quote_exchange = result[0]['equity']
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

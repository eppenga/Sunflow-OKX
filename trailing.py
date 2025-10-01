### Sunflow Cryptobot ###
#
# Traling buy and sell

# Load external libraries
import pprint, requests, threading

# Load internal libraries
from loader import load_config
import database, defs, distance, exchange, orders

# Load config
config = load_config()

# Initialize stuck variable
stuck             = {}
stuck['check']    = True
stuck['time']     = defs.now_utc()[4]
stuck['interval'] = config.stuck_interval

# Initialize order recheck variable
recheck            = {}
recheck['count']   = 0
recheck['maximum'] = 3
   
# Check if we can do trailing buy or sell
def check_order(spot, compounding, active_order, all_buys, all_sells, info):

    # Debug and speed
    debug = False
    speed = False
    stime = defs.now_utc()[4]
    
    # Declare some variables global
    global stuck, recheck
    
    # Initialize variables
    result         = ()
    type_check     = ""
    do_check_order = False
    error_code  = 0
    error_msg   = ""

    # Has current price crossed trigger price
    if active_order['side'] == "Sell":
        if spot <= active_order['trigger']:
            type_check     = "a regular"
            do_check_order = True
    elif active_order['side'] == "Buy":
        if spot >= active_order['trigger']:
            type_check     = "a regular"
            do_check_order = True

    # Check periodically, sometimes orders get stuck
    current_time = defs.now_utc()[4]
    if stuck['check']:
        stuck['check'] = False
        stuck['time']  = defs.now_utc()[4]
    if current_time - stuck['time'] > stuck['interval']:
        type_check = "an additional"
        do_check_order = True

    # Current price crossed trigger price or periodic check
    if do_check_order:

        # Report to stdout
        message = f"Performing {type_check} check on {active_order['side'].lower()} order {active_order['orderid']}'"
        defs.announce(message)

        # Check stuck next time
        stuck['check'] = True
        
        # Has trailing endend, check if order does still exist
        result       = orders.get_order(active_order['orderid'])
        order        = result[0]
        error_code   = result[1]
        error_msg    = result[2]
        if error_code != 0:
            message = f"*** Error: Failed to get trailing order {active_order['orderid']} ***\n>>> Message: {error_code} - {error_msg}"
            defs.log_error(message)
            
        # Check if trailing order is filled (effective at OKX), if so reset counters and close trailing process
        if order['orderStatus'] == "Effective":
            
            # Prepare message for stdout
            defs.announce(f"Trailing {active_order['side'].lower()}: *** Order has been filled! ***")
            message = f"{active_order['side']} order closed for {defs.format_number(active_order['qty'], info['basePrecision'])} {info['baseCoin']} "
            message = message + f"at trigger price {defs.format_number(active_order['trigger'], info['tickSize'])} {info['quoteCoin']}"
            
            # Close trailing process
            result       = close_trail(active_order, all_buys, all_sells, spot, info)
            active_order = result[0]
            all_buys     = result[1]
            all_sells    = result[2]
            closed_order = result[3]
            revenue      = result[4]
        
            # Fill in average price and report message
            if active_order['side'] == "Buy":
                message = message + f" and fill price {defs.format_number(closed_order['avgPrice'], info['tickSize'])} {info['quoteCoin']}"
            elif active_order['side'] == "Sell":
                message = message + f", fill price {defs.format_number(closed_order['avgPrice'], info['tickSize'])} {info['quoteCoin']} "
                message = message + f"and profit {defs.format_number(revenue, info['quotePrecision'])} {info['quoteCoin']}"
            defs.announce(message)
           
            # Report balances and adjust compounding
            compounding['now'] = orders.report_balances(spot, all_buys, info)[0]
                            
            # Report compounding, only possible when balance reporting is active, see config file
            if compounding['enabled']:
                info = defs.calc_compounding(info, spot, compounding)
                
            # Report to revenue log file
            if config.revenue_log:
                defs.log_revenue(active_order, closed_order, revenue, info, config.revenue_log_sides, config.revenue_log_full)
            
        # Check if symbol is spiking
        else:
            result       = check_spike(spot, active_order, order, all_buys, info)
            active_order = result[0]
            all_buys     = result[1]

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return modified data
    return active_order, all_buys, compounding, info

# Checks if the trailing error spiked, order price is either below or above spot depending on side
def check_spike(spot, active_order, order, all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    error_code   = 0
    spike_margin = config.spike_margin

    # Check if the order spiked
    if active_order['side'] == "Sell":

        # Did it spike and was forgotten when selling
        if order['triggerPrice'] > spot * (1 + (spike_margin / 100)):
            defs.announce("*** Warning: Sell order spiked, cancelling current order! ***")
           
            # Remove order from Sunflow
            result       = database.remove(active_order, all_buys, info)
            active_order = result[0]
            all_buys     = result[1]
            error_code   = result[2]
            error_msg    = result[3]

    elif active_order['side'] == "Buy":

        # Did it spike and was forgotten when buying
        if order['triggerPrice'] < spot * (1 - (spike_margin / 100)):
            defs.announce("*** Warning: Buy order spiked, cancelling current order! ***")
            
            # Remove order from Sunflow
            result       = database.remove(active_order, all_buys, info)
            active_order = result[0]
            all_buys     = result[1]
            error_code   = result[2]
            error_msg    = result[3]
    
    if error_code != 0:
        message = f"*** Warning: Order '{active_order['orderid']}' spiked! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return data
    return active_order, all_buys

# Calculate revenue from sell
def calculate_revenue(order, all_sells, spot, info):
    
    # Debug and speed
    debug = True
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    sells         = 0
    buys          = 0
    revenue       = 0
    fees          = {}
    fees['buy']   = 0
    fees['sell']  = 0
    fees['total'] = 0
    
    # Logic
    sells         = order['cumExecValue']
    buys          = sum(item['cumExecValue'] for item in all_sells)
    fees['buy']   = sum(item['cumExecFee'] for item in all_sells) * spot
    fees['buy']   = defs.round_number(fees['buy'], info['quotePrecision'], "down")
    fees['sell']  = order['cumExecFee']
    fees['sell']  = defs.round_number(fees['sell'], info['basePrecision'], "down")
    fees['total'] = fees['buy'] + fees['sell']
    revenue       = sells - buys - fees['total']
    
    # Report to stdout for debug
    if debug:
        message = f"Debug: Total sells {sells} {info['quoteCoin']}, buys {buys} {info['quoteCoin']}, "
        message = message + f"buy fees {fees['buy']} {info['quoteCoin']}, sell fees {fees['sell']} {info['quoteCoin']}, total fees {fees['total']} {info['quoteCoin']}, "
        message = message + f"giving a profit of {defs.format_number(revenue, info['quotePrecision'])} {info['quoteCoin']}"
        defs.announce(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return revenue
    return revenue
    
# Trailing order does not exist anymore, close it
def close_trail(active_order, all_buys, all_sells, spot, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Initialize variables
    revenue = 0
    
    # Make active_order inactive
    active_order['active'] = False
    
    # Get buy or sell order
    result     = orders.get_order(active_order['orderid']) 
    order      = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get order when trying to close trail! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
        return active_order, all_buys, all_sells, order, revenue

    # Add linked order to active_order
    active_order['linkedid'] = order['linkedid']
    
    # Debug to stdout
    if debug:
        defs.announce(f"Active order data:")
        pprint.pprint(active_order)
        print()

    # Get fills for the closed order   
    result     = orders.get_fills(active_order['linkedid'])
    fills      = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code != 0:
        message = f"*** Error: Failed to get fills when trying to close trail! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
        return active_order, all_buys, all_sells, order, revenue

    # Glue order and fills together
    order = orders.merge_order_fills(order, fills, info)
    defs.announce(f"Merged order {active_order['orderid']} with fills from linked SL order {active_order['linkedid']}")

    # Set Sunflow order status to Closed
    order['status'] = "Closed"

    # Debug: Show order
    if debug:
        defs.announce(f"Debug: {active_order['side']} order")
        pprint.pprint(order)
        print()
          
    # Order was bought, create new all buys database
    if order['side'] == "Buy":
        all_buys = database.register_buy(order, all_buys, info)
    
    # Order was sold, create new all buys database, rebalance database and clear all sells
    if order['side'] == "Sell":

        # Debug to stdout
        if debug:
            defs.announce("Debug: All buy orders matching sell order")
            pprint.pprint(all_sells)
            print()

        # Calculate revenue
        revenue = calculate_revenue(order, all_sells, spot, info)
        
        # Create new all buys database
        all_buys = database.register_sell(all_buys, all_sells, info)
                
        # Clear all sells
        all_sells = []

    # Rebalance new database
    if config.database_rebalance:
        all_buys = orders.rebalance(all_buys, info)

    # Report to stdout
    defs.announce(f"Closed trailing {active_order['side'].lower()} order")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return modified data
    return active_order, all_buys, all_sells, order, revenue

# Trailing buy or sell
def trail(spot, compounding, active_order, info, all_buys, all_sells, prices):

    # Debug and speed
    debug = False
    speed = False
    stime = defs.now_utc()[4]
    
    # Initialize variables
    result   = ()
    do_amend = False

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Trailing {active_order['side']}: Checking if we can do trailing")

    # Check if the order still exists
    result       = check_order(spot, compounding, active_order, all_buys, all_sells, info)
    active_order = result[0]
    all_buys     = result[1]
    compounding  = result[2]
    info         = result[3]

    # Order still exists, we can do trailing buy or sell
    if active_order['active']:
       
        # We have a new price
        active_order['previous'] = active_order['current']
                    
        # Determine distance of trigger price
        active_order = distance.calculate(active_order, prices)
                    
        # Calculate new trigger price
        if active_order['side'] == "Sell":
            active_order['trigger_new'] = defs.round_number(spot * (1 - (active_order['fluctuation'] / 100)), info['tickSize'], "down")
        elif active_order['side'] == "Buy":
            active_order['trigger_new'] = defs.round_number(spot * (1 + (active_order['fluctuation'] / 100)), info['tickSize'], "up")

        # Check if we can amend trigger price
        if active_order['side'] == "Sell":
            if active_order['trigger_new'] > active_order['trigger']:
                do_amend = True
        elif active_order['side'] == "Buy":
            if active_order['trigger_new'] < active_order['trigger']:
                do_amend = True

        # Amend trigger price
        if do_amend:
            result       = atp_helper(active_order, all_buys, info)
            active_order = result[0]
            all_buys     = result[1]
        
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return modified data
    return active_order, all_buys, compounding, info

# Change trigger price current trailing sell helper
def aqs_helper(active_order, info, all_sells, all_sells_new):

    # Initialize variables
    debug       = False
    result      = ()
    error_code  = 0
    error_msg   = ""

    # Amend order quantity
    result      = amend_qty_sell(active_order, info)
    response    = result[0]
    error_code  = result[1]
    error_msg   = result[2]

    # Determine what to do based on error code of amend result
    if error_code == 0:

        # Everything went fine, we can continue trailing
        active_order['qty'] = active_order['qty_new']
        message  = f"Adjusted quantity from {defs.format_number(active_order['qty'], info['basePrecision'])} "
        message += f"to {defs.format_number(active_order['qty_new'], info['basePrecision'])} {info['baseCoin']} in {active_order['side'].lower()} order"
        defs.announce(message)
        all_sells = all_sells_new
       
    else:

        # Critical error, log and exit
        message = f"*** Error: Critical failure while trailing! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)

    # Return data
    return active_order, all_sells, all_sells_new

# Change the quantity of the current trailing sell
def amend_qty_sell(active_order, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""

    # Report to stdout
    message = f"Trying to adjust quantity from {defs.format_number(active_order['qty'], info['basePrecision'])} "
    message = message + f"to {defs.format_number(active_order['qty_new'], info['basePrecision'])} {info['baseCoin']}"
    defs.announce(message)

    # Amend order for quantity
    result     = exchange.amend_order(active_order['orderid'], 0, active_order['qty_new'])
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code != 0:
        message = f"*** Warning: Something went wrong when trying to amend the quantity! ***"
        defs.log_error(message)
        return response, error_code, error_msg

    # Debug to stdout
    if debug:
        defs.announce("Debug: Amended quantity sell order")
        pprint.pprint(response)
        print()

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return error code 
    return response, error_code, error_msg

# Change quantity trailing sell helper
def atp_helper(active_order, all_buys, info):

    # Initialize variables
    debug      = False
    result     = ()
    response   = {}
    error_code = 0
    error_msg = ""
    
    # Amend trigger price
    result     = amend_trigger_price(active_order, info)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]

    # Determine what to do based on error code of amend result
    if error_code == 0:

        # Everything went fine, we can continue trailing
        message  = f"Adjusted trigger price from {defs.format_number(active_order['trigger'], info['tickSize'])} to "
        message += f"{defs.format_number(active_order['trigger_new'], info['tickSize'])} {info['quoteCoin']} in {active_order['side'].lower()} order"
        defs.announce(message)
        active_order['trigger'] = active_order['trigger_new']        

    elif (error_code == 51280) or (error_code == 51278):
    
        # Order went up to fast, SL order couldnt keep up, reset and replace
        # error_code = 51280 - SL trigger price must be less than the last price
        # error_code = 51278 - SL trigger price cannot be lower than the last price
        message = f"*** Warning: Order couldn't keep up, trailing cancelled ***\n>>> Message: {error_code} - {error_msg}"
        defs.announce(message)

        # Try to remove order
        result       = database.remove(active_order, all_buys, info)
        active_order = result[0]
        all_buys     = result[1]
        error_code   = result[2]
        error_msg    = result[3]
        if error_code !=0:
            message = f"*** Warning: Trying to remove order while trailing ***\n>>> Message: {error_code} - {error_msg}"
            defs.log_error(message)
    
    else:

        # Critical error, log and exit
        message = f"*** Error: Critical failure while trailing! ***\n>>> Message: {error_code} - {error_msg}"
        defs.log_error(message)
    
    # Return active_order
    return active_order, all_buys

# Change the trigger price of the current trailing sell
def amend_trigger_price(active_order, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    response   = {}
    result     = ()
    error_code = 0
    error_msg  = ""
       
    # Report to stdout
    message = f"Trying to adjust trigger price from {defs.format_number(active_order['trigger'], info['tickSize'])} to "
    message = message + f"{defs.format_number(active_order['trigger_new'], info['tickSize'])} {info['quoteCoin']}"
    defs.announce(message)
   
    # Amend order for price
    result     = exchange.amend_order(active_order['orderid'], active_order['trigger_new'], 0)
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    if error_code != 0:
        message = f"*** Warning: Something went wrong when trying to amend the price! ***"
        defs.log_error(message)
        return response, error_code, error_msg
 
    # Debug to stdout
    if debug:
        defs.announce("Debug: Amended trigger price order")
        pprint.pprint(response)
        print()
        
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return error code 
    return response, error_code, error_msg

### Sunflow Cryptobot ###
#
# Do database things

# Load external libraries
import pprint, json

# Load internal libraries
from loader import load_config
import defs, orders

# Load config
config = load_config()

# Create a new all buy database file
def save(all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    count  = 0
    total  = 0
    result = ()

    # Write the file
    with open(config.dbase_file, 'w', encoding='utf-8') as json_file:
        json.dump(all_buys, json_file)

    # Get statistics and output to stdout
    result = order_count(all_buys, info)
    count  = result[0]
    total  = result[1]
    defs.announce(f"Database contains {count} buy orders and {total} {info['baseCoin']} was bought")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return
    return
    
# Load the database with all buys
def load(dbase_file, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    all_buys = []

    # Load existing database file
    try:
        with open(dbase_file, 'r', encoding='utf-8') as json_file:
            all_buys = json.load(json_file)
    except FileNotFoundError:
        defs.announce("Database with all buys not found, exiting...")
        defs.halt_sunflow = True
        exit()
    except json.decoder.JSONDecodeError:
        defs.announce("Database with all buys not yet filled, may come soon!")

    # Get statistics and output to stdout
    result = order_count(all_buys, info)
    defs.announce(f"Database contains {result[0]} buy orders and {defs.format_number(result[1], info['basePrecision'])} {info['baseCoin']} was bought")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return database
    return all_buys

# Remove an order, sets active_order to False and adjusts all_buys
def remove(active_order, all_buys, info):
    
    # Debug
    debug = False
    
    # Initialize variables
    result     = ()
    response   = {}
    error_code = 0
    error_msg  = ""
    
    # Debug
    if debug:
        defs.announce(f"Debug: About to remove {active_order['side']} order {active_order['orderid']}")
    
    # Reset active_order
    active_order['active'] = False
    
    # Remove order from exchange, error handling is happening in next functions
    result     = orders.cancel_order(active_order['orderid'])
    response   = result[0]
    error_code = result[1]
    error_msg  = result[2]
    
    # Remove order from database
    if active_order['side'] == "Buy":
        all_buys = remove_buy(active_order['orderid'], all_buys, info)

    # Rebalance if allowed
    if config.database_rebalance:
        all_buys = orders.rebalance(all_buys, info)
    
    # Return
    return active_order, all_buys, error_code, error_msg

# Remove an order from the all buys database file
def remove_buy(orderid, all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Initialize variables
    all_buys_new = []
    order_found  = False
    
    # Remove the order
    for loop_buy in all_buys:
        if loop_buy['orderid'] != orderid:
            order_found = True
            all_buys_new.append(loop_buy)

    # Check if order was found
    if order_found:
        # Save to database
        save(all_buys_new, info)
        defs.announce(f"Order {orderid} was removed from all_buys database!")    
    else:
        all_buys_new = all_buys
        defs.announce(f"Order {orderid} was not found in all_buys database!")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return database
    return all_buys_new

# Register all buys in a database file
def register_buy(buy_order, all_buys, info):

    debug = False
    speed = False
    stime = defs.now_utc()[4]

    # Initialize variables
    found        = False
    all_buys_new = []

    # Check if order already exists in all buys database
    for existing in all_buys:
        if existing['orderid'] == buy_order['orderid']:
            all_buys_new.append(buy_order)
            found = True
        else:
            all_buys_new.append(existing)

    # If not found, add as new order
    if not found:
        all_buys_new.append(buy_order)

    # Save to database
    save(all_buys_new, info)

    # Report to stdout
    defs.announce("Registered 1 order via trailing buy")

    # Debug to stdout
    if debug:
        defs.announce("Debug: This was the new buy order that was added to the database:")
        pprint.pprint(buy_order)
        print()

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return new all_buys database
    return all_buys_new

# Remove all sold buy orders from the database file
def register_sell(all_buys, all_sells, info):
    
    # Debug
    debug = False
    speed = False
    stime = defs.now_utc()[4]
    
    # Initialize variables
    unique_ids   = 0
    all_buys_new = []
    
    # Get a set of all sell order IDs for efficient lookup
    sell_order_ids = {sell['orderid'] for sell in all_sells}

    # Filter out all_buys entries that have their orderid in sell_order_ids
    all_buys_new = [buy for buy in all_buys if buy['orderid'] not in sell_order_ids]

    # Count unique order ids
    unique_ids = len(sell_order_ids)
    
    # Save to database
    save(all_buys_new, info)

    # Report to stdout
    defs.announce(f"Registered {unique_ids} orders via trailing sell")
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: These were new sell order(s) that were removed from the database:")
        pprint.pprint(all_sells)
        print()
    
    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return the cleaned buys
    return all_buys_new

# Determine number of orders and qty
def order_count(all_buys, info):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Get number of orders
    order_count = len(all_buys)
    total_qty   = sum(item['cumExecQty'] for item in all_buys)
    total_qty   = defs.round_number(total_qty, info['basePrecision'], "down")

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Order count is {order_count} abd total quantity is {total_qty}")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return data
    return order_count, total_qty
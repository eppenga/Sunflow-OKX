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

    # Write the file
    with open(config.dbase_file, 'w', encoding='utf-8') as json_file:
        json.dump(all_buys, json_file)

    # Get statistics and output to stdout
    result = order_count(all_buys, info)
    defs.announce(f"Database contains {result[0]} buy orders and {defs.format_number(result[1], info['basePrecision'])} {info['baseCoin']} was bought")

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
    error_code = 0
    
    # Debug
    if debug:
        defs.announce(f"Debug: About to remove {active_order['side']} order {active_order['orderid']}")
    
    # Reset active_order
    active_order['active'] = False
    
    # Remove order from exchange
    error_code = orders.cancel_order(active_order['orderid'])
    
    # Remove order from database
    if active_order['side'] == "Buy":
        all_buys = remove_buy(active_order['orderid'], all_buys, info)

    # Rebalance if allowed
    if config.database_rebalance:
        all_buys = orders.rebalance(all_buys, info)
    
    # Return
    active_order, all_buys, error_code

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

    # Debug
    debug = False
    speed = False
    stime = defs.now_utc()[4]

    # Initialize variables
    counter       = 0
    all_buys_new  = []
    loop_buy      = False
    loop_appended = False
    
    # Check if order already exists in all buys database
    for loop_buy in all_buys:
        if loop_buy['orderid'] == buy_order['orderid']:
            counter = counter + 1
            loop_appended = True
            loop_buy = buy_order
        all_buys_new.append(loop_buy)
    
    # If not found in all buys database, then add new buy order
    if not loop_appended:
        all_buys_new.append(buy_order)
        counter = counter + 1
      
    # Debug to stdout
    if debug:
        defs.announce(f"Debug: New database with {counter} buy orders")
        print(all_buys_new)
        print()

    # Save to database
    save(all_buys_new, info)    

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return new buy database
    return all_buys_new

# Remove all sold buy orders from the database file
def register_sell(all_buys, all_sells, info):
    
    # Debug
    debug = False
    speed = False
    stime = defs.now_utc()[4]
    
    # Initialize variables
    unique_ids = 0
    
    # Get a set of all sell order IDs for efficient lookup
    sell_order_ids = {sell['orderid'] for sell in all_sells}

    # Filter out all_buys entries that have their orderid in sell_order_ids
    filtered_buys = [buy for buy in all_buys if buy['orderid'] not in sell_order_ids]

    # Count unique order ids
    unique_ids = len(sell_order_ids)
    
    # Save to database
    save(filtered_buys, info)
    
    # Debug to stdout
    if debug:
        print("All sell orders")
        pprint.pprint(all_sells)
        
        print("\nRemoved these unique ids")
        pprint.pprint(sell_order_ids)
        
        print("\nNew all buys database")
        pprint.pprint(filtered_buys)
        print()
    
    # Report to stdout
    defs.announce(f"Sold {unique_ids} orders via trailing sell")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return the cleaned buys
    return filtered_buys

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

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return data
    return order_count, total_qty
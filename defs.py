### Sunflow Cryptobot ###
#
# General functions

# Load external libraries
from pathlib import Path
from datetime import datetime, timezone
import inspect, math, pprint, pytz, time

# Load internal libraries
from loader import load_config
import defs, indicators, preload

# Load config
config = load_config()

# Initialize variables 
df_errors    = 0        # Dataframe error counter
halt_sunflow = False    # Register halt or continue

# Add new kline and remove the oldest
def new_kline(kline, klines):

    # Add new kline
    klines['time'].append(kline['time'])
    klines['open'].append(kline['open'])
    klines['high'].append(kline['high'])
    klines['low'].append(kline['low'])
    klines['close'].append(kline['close'])
    klines['volume'].append(kline['volume'])
    klines['turnover'].append(kline['turnover'])
    
    # Remove first kline
    klines['time'].pop(0)
    klines['open'].pop(0)
    klines['high'].pop(0)
    klines['low'].pop(0)
    klines['close'].pop(0)
    klines['volume'].pop(0)
    klines['turnover'].pop(0)

    # Return klines
    return klines

# Remove the first kline and replace with fresh kline
def update_kline(kline, klines): 

    # Remove last kline
    klines['time'].pop()
    klines['open'].pop()
    klines['high'].pop()
    klines['low'].pop()
    klines['close'].pop()
    klines['volume'].pop()
    klines['turnover'].pop()
    
    # Add new kline
    klines['time'].append(kline['time'])
    klines['open'].append(kline['open'])
    klines['high'].append(kline['high'])
    klines['low'].append(kline['low'])
    klines['close'].append(kline['close'])
    klines['volume'].append(kline['volume'])
    klines['turnover'].append(kline['turnover'])

    # Return klines
    return klines

# Update matching kline based on time
def add_kline(kline, klines):

    # Find the index
    if kline['time'] in klines['time']:
        index = klines['time'].index(kline['time'])
        
        # Override the values
        klines['open'][index]     = kline['open']
        klines['high'][index]     = kline['high']
        klines['low'][index]      = kline['low']
        klines['close'][index]    = kline['close']
        klines['turnover'][index] = kline['turnover']
        klines['volume'][index]   = kline['volume']
    
    # Return klines
    return klines

# Check if there are no adjacent orders already 
def check_spread(all_buys, spot, spread):

    # Debug
    debug = False

    # Initialize variables
    near    = 0
    can_buy = True

    # Get the boundaries
    min_price = spot * (1 - (spread / 100))
    max_price = spot * (1 + (spread / 100))

    # Loop through the all_buys
    for order in all_buys:
        avg_price = order["avgPrice"]
        if (avg_price >= min_price) and (avg_price <= max_price):
             can_buy = False
             near = min(abs((avg_price / min_price * 100) - 100), abs((avg_price / max_price * 100) - 100))
             break
         
    # Debug to stdout
    if debug:
        if can_buy:
            defs.announce("Debug: No adjacent order found, we can buy")
        else:
            defs.announce("Debug: Adjacent order found, we can't buy")

    # Return buy advice
    return can_buy, near

# Return timestamp according to UTC and offset
def now_utc():
    
    # Current UTC datetime
    current_time = datetime.now(timezone.utc)
    milliseconds = math.floor(current_time.microsecond / 10000) / 100
    timestamp_0  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_1  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | " + config.symbol + ": "
    timestamp_2  = milliseconds
    timestamp_3  = str(milliseconds) + " | "
    timestamp_4  = int(time.time() * 1000)

    # Convert current UTC time to the specified local timezone
    local_tz = pytz.timezone(config.timezone_str)
    local_time = current_time.astimezone(local_tz)
    
    # Current local time
    timestamp_5  = local_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_6  = local_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | " + config.symbol + ": "
    
    return timestamp_0, timestamp_1, timestamp_2, timestamp_3, timestamp_4, timestamp_5, timestamp_6

# Log all responses from exchange
def log_exchange(response, message):
    
    # Debug
    debug = False
    
    # Initialize variables
    to_log        = ""
    response_nice = {}
    
    # Create log message   
    to_log = message + "\n"
    
    # Extend log message based on error level
    if config.exchange_log_full:
        response_nice = pprint.pformat(response)
        to_log = message + "\n" + response_nice + "\n\n"
    
    # Write to exchange log file
    if config.exchange_log:    
        with open(config.exchange_file, 'a', encoding='utf-8') as file:
            file.write(to_log)

# Log all errors
def log_error(exception):
    
    # Debug
    debug = False

    # Declare global variables
    global halt_sunflow
    
    # Debug to stdout
    if debug:
        defs.announce("Debug:")
        print("Exception RAW:")
        print(exception)
        print()
       
    # Initialize variables
    halt_execution = True
    stack          = inspect.stack()
    call_frame     = stack[1]
    filename       = Path(call_frame.filename).name
    functionname   = call_frame.function
    timestamp      = now_utc()[6]

    # Safeguard from type errors
    exception = str(exception)

    # Create message
    message = timestamp + f"{filename}: {functionname}: {exception}"

    # Just a warning
    if "Warning" in exception:
        halt_execution = False
      
    # Error: Dataframe failure
    if ("(30908)" in exception) or ("Length of values" in exception) or ("All arrays must be of the same length" in exception):
        defs.announce(f"*** Warning: Dataframe issue for the {df_errors + 1} time! ***")
        halt_execution = False
       
    # Write to error log file
    with open(config.error_file, 'a', encoding='utf-8') as file:
        file.write(message + "\n\n")
    
    # Report to stdout
    defs.announce(f"{exception} | File: {filename} | Function: {functionname}")
    
    # Terminate hard
    if halt_execution:
        defs.announce("*** Error Terminating Sunflow! ***")
        defs.announce(exception)
        halt_sunflow = True

# Log revenue data
def log_revenue(active_order, order, revenue, info, sides=True, extended=False):
    
    # Debug
    debug = False
  
    # Initialize variables
    message   = "Something went wrong while logging revenue..."
    divider   = "================================================================================\n"
    seperator = "\n----------------------------------------\n"
    timestamp = defs.now_utc()[0]
    
    # Round two variables
    revenue               = defs.round_number(revenue, info['quotePrecision'])
    order['cumExecValue'] = defs.round_number(order['cumExecValue'], info['quotePrecision'])

    # Check if we can log
    if (not extended) and (not sides) and (order['side'] == "Buy"):
        return

    # Format data for extended messaging
    if extended:
        timedis = "timestamp\n" + timestamp
        a_order = "active_order\n" + pprint.pformat(active_order)
        t_order = "order\n" + pprint.pformat(order)
        r_order = "revenue\n" + pprint.pformat(revenue)
        i_order = "info\n" + pprint.pformat(info)
        message = divider + timedis+ seperator + a_order + seperator + t_order + seperator + r_order + seperator + i_order

    # Format data for normal messaging
    # UTC Time, createdTime, orderid, linkedid, side, symbol, baseCoin, quoteCoin, orderType, orderStatus, avgPrice, qty, trigger_ini, triggerPrice, cumExecFeeCcy, cumExecFee, cumExecQty, cumExecValue, revenue
    if not extended:
        message = f"{timestamp},{order['createdTime']},"
        message = message + f"{order['orderid']},{order['linkedid']},"
        message = message + f"{order['side']},{order['symbol']},{info['baseCoin']},{info['quoteCoin']},"
        message = message + f"{order['orderType']},{order['orderStatus']},"
        message = message + f"{order['avgPrice']},{order['qty']},{active_order['trigger_ini']},{order['triggerPrice']},"
        message = message + f"{order['cumExecFeeCcy']},{order['cumExecFee']},{order['cumExecQty']},{order['cumExecValue']},{revenue}"
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Revenue log file message")
        print(message)
    
    # Write to revenue log file
    with open(config.revenue_file, 'a', encoding='utf-8') as file:
        file.write(message + "\n")
        
    # Return
    return

# Outputs a (Pass) or (Fail) for decide_buy()
def report_buy(result):

    # Initialize variable
    pafa = "(No buy)"

    # Logic
    if result:
        pafa = "(Buy)"
    else:
        pafa = "(No buy)"

    # Return result
    return pafa

# Give an advice via the buy matrix
def advice_buy(indicators_advice, orderbook_advice, trade_advice, pricelimit_advice, use_indicators, use_spread, use_orderbook, use_trade, use_pricelimit, spot, all_buys, interval_index):

    # Initialize variables
    spread_advice          = {}
    technical_indicators   = {}
    result                 = ()
    klines                 = use_indicators['klines']


    '''' Check TECHNICAL INDICATORS for buy decission '''
    
    if use_indicators['enabled']:
        indicators_advice[interval_index]['filled'] = True
        technical_indicators                        = indicators.calculate(klines[interval_index], spot)
        result                                      = indicators.advice(technical_indicators)
        indicators_advice[interval_index]['value']  = result[0]
        indicators_advice[interval_index]['level']  = result[1]

        # Check if indicator advice is within range
        if (indicators_advice[interval_index]['value'] >= use_indicators['minimum']) and (indicators_advice[interval_index]['value'] <= use_indicators['maximum']):
            indicators_advice[interval_index]['result'] = True
        else:
            indicators_advice[interval_index]['result'] = False
    else:
        # If indicators are not enabled, always true
        indicators_advice[interval_index]['result'] = True

    
    ''' Check SPREAD for buy decission '''
    
    if use_spread['enabled']:
        result                   = defs.check_spread(all_buys, spot, use_spread['distance'])
        spread_advice['result']  = result[0]
        spread_advice['nearest'] = result[1]
    else:
        # If spread is not enabled, always true
        spread_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''
    
    if use_orderbook['enabled']:
        if (orderbook_advice['buy_perc'] >= use_orderbook['minimum']) and (orderbook_advice['buy_perc'] <= use_orderbook['maximum']):
            orderbook_advice['result'] = True
        else:
            orderbook_advice['result'] = False
    else:
        # If orderbook is not enabled, always true
        orderbook_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''
    
    if use_trade['enabled']:
        if (trade_advice['buy_ratio'] >= use_trade['minimum']) and (trade_advice['buy_ratio'] <= use_trade['maximum']):
            trade_advice['result'] = True
        else:
            trade_advice['result'] = False
    else:
        # If orderbook is not enabled, always true
        trade_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''

    if use_pricelimit['enabled']:
        if use_pricelimit['max_buy_enabled']:
            if spot < use_pricelimit['max_buy']:
                pricelimit_advice['buy_result'] = True
            else:
                pricelimit_advice['buy_result'] = False
    else:
        # If pricelimit is not enabled, always true
        pricelimit_advice['buy_result'] = True
        
    # Return all data
    return indicators_advice, spread_advice, orderbook_advice, trade_advice, pricelimit_advice

# Calculate the average of all active intervals
def indicators_average(indicators_advice, use_indicators):
    
    # Debug
    debug  = False
    
    # Initialize variables
    count          = 0
    total_value    = 0
    average_filled = True
    average_level  = "Neutral"
    average_result = False
    average_value  = 0
    intervals      = use_indicators['intervals']
    
    # Exclude index 0 and empty selections; keep numeric keys (1,2,3,...)
    filtered_intervals = {i: label for i, label in intervals.items() if i != 0 and label}

    # Check if all required intervals are filled
    required_idxs = list(filtered_intervals.keys())
    average_filled = bool(required_idxs) and all(
        indicators_advice.get(i, {}).get('filled', False)
        for i in required_idxs
    )

    # Calculate the average value only if all selected intervals are filled
    if average_filled:
        values = [float(indicators_advice[i]['value']) for i in required_idxs]
        count = len(values)
        total_value = sum(values)
        average_value = total_value / count if count else 0.0

        # Derive level & result (assuming these exist in your environment)
        average_level = indicators.technicals_advice(average_value)
        average_result = (use_indicators['minimum'] <= average_value <= use_indicators['maximum'])

    # Assign average indicators into index 0
    indicators_advice[0].update({
        'filled': average_filled,
        'level':  average_level if average_filled else "Neutral",
        'result': average_result if average_filled else False,
        'value':  average_value if average_filled else 0.0,
    })

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Dump of intervals advice variable:")
        pprint.pprint(indicators_advice)
        pprint.pprint(intervals)
       
    return indicators_advice

# Determines buy decission and outputs to stdout
def decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, trade_advice, use_trade, pricelimit_advice, use_pricelimit, interval_index, info):
            
    # Debug
    debug = False

    # Initialize variables
    do_buy    = {}
    do_buy[1] = False   # Indicator interval 1
    do_buy[2] = False   # Indicator interval 2
    do_buy[3] = False   # Indicator interval 3
    do_buy[4] = False   # Spread
    do_buy[5] = False   # Orderbook
    do_buy[6] = False   # Trades
    do_buy[7] = False   # Pricelimit
    can_buy   = False
    message   = ""
    interval  = use_indicators['intervals'][interval_index]
    intervals = use_indicators['intervals']
    
    # Report and check indicators
    if use_indicators['enabled']:
        
        # Add to message
        message += f"Update {interval}: "

        # Use average of all active intervals
        if config.indicators_average:        

            # Calculate average
            indicators_advice = indicators_average(indicators_advice, use_indicators)
            do_buy[1] = indicators_advice[0]['result']
            do_buy[2] = indicators_advice[0]['result']
            do_buy[3] = indicators_advice[0]['result']
                        
            # Create message
            for i in range(1, 4):
                if intervals[i] != '':
                    message += f"{intervals[i]}: "
                    if indicators_advice[i]['filled']:
                        message +=  f"{indicators_advice[i]['value']:.2f}, " 
                    else:
                        message += "?, "
            if indicators_advice[0]['filled']:
                message += f"average: {indicators_advice[0]['value']:.2f} "
            else:
                message += "average: ? "
            message += report_buy(indicators_advice[0]['result']) + ", "

        # Use all intervals seperatly
        if not config.indicators_average:

            # Create message
            for i in range(1, 4):
                if intervals[i] != '':
                    if indicators_advice[i]['result']:
                        do_buy[i] = True
                    message += f"{intervals[i]}: "
                    if indicators_advice[i]['filled']:
                        message += f"{indicators_advice[i]['value']:.2f} " 
                    else:
                        message += "? "
                    message += report_buy(indicators_advice[i]['result']) + ", "
                else:
                    do_buy[i] = True
    else:
        # Indicators are disabled
        do_buy[1] = True
        do_buy[2] = True
        do_buy[3] = True

    # Report spread
    if use_spread['enabled']:
        if spread_advice['result']:
            do_buy[4] = True
        message += f"Spread: {spread_advice['nearest']:.4f} % "
        message += report_buy(spread_advice['result']) + ", "
    else:
        do_buy[4] = True
    
    # Report orderbook
    if use_orderbook['enabled']:
        if orderbook_advice['result']:
            do_buy[5] = True
        message += f"Orderbook: {orderbook_advice['buy_perc']:.2f} % "
        message += report_buy(orderbook_advice['result']) + ", "
    else:
        do_buy[5] = True

    # Report trades
    if use_trade['enabled']:
        if trade_advice['result']:
            do_buy[6] = True
        message += f"Trade: {trade_advice['buy_ratio']:.2f} % "
        message += report_buy(trade_advice['result']) + ", "
    else:
        do_buy[6] = True

    # Report pricelimit
    if use_pricelimit['enabled']:
        if pricelimit_advice['buy_result']:
            do_buy[7] = True
        message += f"Max buy: {defs.format_number(use_pricelimit['max_buy'], info['tickSize'])} {info['quoteCoin']} "
        message += report_buy(pricelimit_advice['buy_result']) + ", "
    else:
        do_buy[7] = True

    # Determine buy decission
    if do_buy[1] and do_buy[2] and do_buy[3] and do_buy[4] and do_buy[5] and do_buy[6] and do_buy[7]:
        can_buy = True
        message += "BUY!"
    else:
        can_buy = False
        message += "NO BUY"

    # Debug to stdout
    if debug:
        print("\n\n*** Simplified buy reporting ***\n")

        print("Intervals:")
        print(intervals, "\n")

        print("Indicator advice:")
        print(indicators_advice, "\n")
        
        print("Spread advice:")
        print(spread_advice, "\n")
        
        print("Orderbook advice:")
        print(orderbook_advice, "\n")

        print("Pricelimit advice:")
        print(pricelimit_advice, "\n")

    # Return result
    return can_buy, message, indicators_advice

# Report ticker info to stdout
def report_ticker(spot, new_spot, rise_to, active_order, all_buys, info):

    # Create message
    message = "Price went "
    if new_spot > spot:
        message += "up"
    else:
        message += "down"
    
    message += f" from {format_number(spot, info['tickSize'])} to {format_number(new_spot, info['tickSize'])} {info['quoteCoin']}"

    if active_order['active']:
        trigger_distance = abs(new_spot - active_order['trigger'])
        trigger_distance = defs.format_number(trigger_distance, info['tickSize'])
        message += f", trigger price distance is {trigger_distance} {info['quoteCoin']}"

    if not active_order['active']:
        if rise_to:
            message += f", needs to rise {rise_to}, NO SELL"
        else:
            if len(all_buys) > 0:
                message += ", SELL"
    
    # Return message
    return message

# Report on compounding
def calc_compounding(info, spot, compounding):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Calculate ratio
    compounding_ratio = compounding['now'] / compounding['start']
    
    # Profitable or not
    if compounding_ratio > 0:

        # Adjust minimum order values
        info = preload.calc_info(info, spot, config.multiplier, compounding)

        # Create message
        message = f"Compounding started at {defs.format_number(compounding['start'], info['quotePrecision'])} {info['quoteCoin']}, "
        message = message + f"currently {defs.format_number(compounding['now'], info['quotePrecision'])} {info['quoteCoin']}, "
        message = message + f"ratio is {compounding_ratio:.4f}x"

    else:
        message = "Compounding inactive because no profit yet"
        
    # Display message
    defs.announce(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return
    return info

# Send out a notification via stdout
def announce(message):
   
    # Initialize variables
    stack        = inspect.stack()
    call_frame   = stack[1]
    filename     = Path(call_frame.filename).name
    functionname = call_frame.function
    
    # Local or UTC time
    if config.timeutc_std:
        timestamp = now_utc()[1]
    else:
        timestamp = now_utc()[6]

    # Safeguard from type errors
    message = str(message)

    # Check if we can notify for blanc messages
    if not message:
        message_none = timestamp + f"{filename}: {functionname}: No announcement available"
        return message_none

    # Message for stdout
    message_stdout = timestamp + f"{filename}: {functionname}: {message}"    

    # Check if we can notify for session messages
    if not config.session_report and "session:" in message:
        return message_stdout
         
    # Report to stdout
    print(message_stdout + "\n")
    
    # Return message
    return message_stdout

# Round value to the nearest step size
def round_number(value, step_size, rounding = ""):
    
    # Logic
    if step_size < 1:
        decimal_places = -int(math.log10(step_size))
        factor = 10 ** decimal_places
    else:
        factor = 1 / step_size

    # Round down
    if rounding == "down":
        rounded_value = math.floor(value * factor) / factor
    
    # Round up
    if rounding == "up":
        rounded_value = math.ceil(value * factor) / factor
    
    # Round half
    if not rounding:
        rounded_value = round(value * factor) / factor

    # Return rounded value
    return rounded_value

# Formats the price according to the ticksize.
def format_number(price, tickSize):

    # Check for number format
    modified_tickSize = scientific_to_decimal_str(tickSize)

    # Calculate the number of decimal places from ticksize
    decimal_places = get_decimal_places(modified_tickSize)
    
    # Format the price with the calculated decimal places
    formatted_price = f"{price:.{decimal_places}f}"
    
    # Return formatted price
    return formatted_price

# Returns the number of decimal places based on the ticksize value.
def get_decimal_places(ticksize_str):

    if '.' in ticksize_str:
        decimal_places = len(ticksize_str.split('.')[1])
    else:
        decimal_places = 0

    # Return decimal places
    return decimal_places

def scientific_to_decimal_str(number):
    # Convert the number to string
    number_str = str(number)
    
    # Check if it contains 'e' or 'E', which indicates scientific notation
    if 'e' in number_str or 'E' in number_str:
        # Convert the scientific notation number to a float and then to a decimal string
        decimal_str = f"{float(number):.10f}".rstrip('0').rstrip('.')
    else:
        # If it's not in scientific notation, just return it as a string with appropriate formatting
        decimal_str = f"{number:.10f}".rstrip('0').rstrip('.')
    
    return decimal_str
    
# Calculates the closest index
def get_closest_index(data, span):
    
    # Find the closest index in the time {timeframe}
    closest_index = None
    min_diff = float('inf')

    for i, t in enumerate(data['time']):
        diff = abs(t - span)
        if diff < min_diff:
            min_diff = diff
            closest_index = i

    # Return closest index
    return closest_index

# Calcuate number of items to use
def get_index_number(data, timeframe, limit):
    
    # Time calculations
    latest_time  = data['time'][-1]           # Get the time for the last element
    span         = latest_time - timeframe    # Get the time of the last element minus the timeframe
    
    # Calculate number of items to use
    missing  = 0
    elements = len(data['time'])
    ratio = (elements / limit) * 100
    if elements < limit:
        missing = limit - elements
        defs.announce(f"*** Warning: Still fetching data, message will disappear ({ratio:.0f} %)! ***")
    
    closest_index = defs.get_closest_index(data, span)
    number        = limit - closest_index - missing
    
    # Return number
    return number

# Caculate the average value in a list
def average(numbers):

    # Logic
    if not numbers:
        return 0
    
    total = sum(numbers)
    count = len(numbers)
    average = total / count

    # Return average
    return average

# Calculate average buy and sell percentage for timeframe
def average_depth(depth_data, use_orderbook, buy_percentage, sell_percentage):

    # Debug
    debug_1 = False
    debug_2 = False

    # Initialize variables
    datapoints   = {}
    
    # Number of depth elements to use
    number = defs.get_index_number(depth_data, use_orderbook['timeframe'], use_orderbook['limit'])

    # Validate data
    datapoints['depth']   = number
    datapoints['compare'] = len(depth_data['time'])
    datapoints['limit']   = use_orderbook['limit']
    if (datapoints['depth'] >= datapoints['compare']) and (datapoints['compare'] >= datapoints['limit']):
        defs.announce("*** Warning: Increase orderbook_limit variable in config file! ***")
    
    # Debug elements
    if debug_1:
        print("All elements")
        pprint.pprint(depth_data['buy_perc'])
        print(f"Last {number} elements")
        pprint.pprint(depth_data['buy_perc'][(-number):])

    # Calculate average depth
    if datapoints['compare'] >= datapoints['limit']:
        new_buy_percentage  = defs.average(depth_data['buy_perc'][(-number):])
        new_sell_percentage = defs.average(depth_data['sell_perc'][(-number):])
    else:
        new_buy_percentage  = buy_percentage
        new_sell_percentage = sell_percentage
    
    # Debug announcement
    if debug_2: 
            message = f"Currently {datapoints['compare']} / {datapoints['limit']} data points, "
            message = message + f"using the last {datapoints['depth']} points and "
            message = message + f"buy percentage is {new_buy_percentage:.2f} %"
            defs.announce(message)

    # Return data
    return new_buy_percentage, new_sell_percentage

# Calculate total buy and sell from trades
def calculate_total_values(trades):

    # Initialize variables
    total_sell = 0.0
    total_buy  = 0.0
    total_all  = 0.0 

    # Do logic
    for i in range(len(trades['price'])):
        price = float(trades['price'][i])
        size  = float(trades['size'][i])
        value = price * size

        if trades['side'][i] == 'Sell':
            total_sell += value
        elif trades['side'][i] == 'Buy':
            total_buy += value

    # Calculate total
    total_all = total_buy + total_sell
    
    # Return totals
    return total_buy, total_sell, total_all, (total_buy / total_all) * 100, (total_sell / total_all) * 100

# Report time it took to execute a function
def report_exec(start_time, supplement = "", always_display = False):
       
    # Initialize variables
    message    = ""
    mess_delay = config.func_norm_delay
    warn_delay = config.func_warn_delay
    end_time   = now_utc()[4]
    exec_time  = end_time - start_time
    
    # Overrule always_display
    if config.func_show_delay:
        always_display = True
    
    # Create message
    if exec_time > mess_delay or always_display:
        message = f"Execution time of function was {exec_time} ms"
        if supplement:
            message = message + f" ({supplement})"
        if exec_time > warn_delay:
            message = "*** Warning " + message + "! ***"
        
    # Return message
    return message

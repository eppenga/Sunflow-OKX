### Sunflow Cryptobot ###
#
# Decode data from exchange

# Load external libraries
from loader import load_config
import pprint

# Load internal libraries
import defs

# Load config
config = load_config()

# Decode order ID
def orderid(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    orderid = ""

    # Debug
    if debug:
        defs.announce(f"Debug: Before decode order ID:")
        pprint.pprint(response)
        print()
    
    # Mapping order ID
    orderid = int(response['data'][0]['algoId'])
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decoded order ID: {orderid}")
    
    # Return order ID
    return orderid

# Decode ticker
def ticker(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    ticker = {'time': 0, 'symbol': config.symbol, 'lastPrice': 0}

    # Debug
    if debug:
        defs.announce(f"Debug: Before decode ticker:")
        pprint.pprint(response)
        print()
    
    # Mapping ticker
    ticker['time']      =   int(response['data'][0]['ts'])
    ticker['symbol']    =       response['data'][0]['instId']
    ticker['lastPrice'] = float(response['data'][0]['last'])
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decode ticker:")
        pprint.pprint(ticker)
        print()
    
    # Return ticker
    return ticker
    
# Decode klines
def klines(response):
        
    # Debug
    debug = False
    
    # Initialize variables
    row    = {}
    klines = {'time': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'turnover': [], 'status': []}
    
    # Debug
    if debug:
        defs.announce(f"Debug: Before decode klines:")
        pprint.pprint(response)
        print()

    # Mapping klines
    for row in response['data']:
        klines['time'].append(int(row[0]))            # Time (timestamp in ms)
        klines['open'].append(float(row[1]))          # Open price
        klines['high'].append(float(row[2]))          # High price
        klines['low'].append(float(row[3]))           # Low price
        klines['close'].append(float(row[4]))         # Close price
        klines['volume'].append(float(row[5]))        # Volume (base quantity)
        klines['turnover'].append(float(row[7]))      # Turnover (base * quote quantity)
        klines['status'].append(int(row[8]))          # Kline state (0 is incomplete, 1 is complete)
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decoded klines:")
        pprint.pprint(klines)
        print()
    
    # Return klines
    return klines

# Decode instrument info
def info(response):

    # Debug
    debug = False
    
    # Initialize variables
    info       = {}
    instrument = response['data'][0]
    
    # Debug
    if debug:
        defs.announce(f"Debug: Before decode instrument info:")
        pprint.pprint(response)
        print()

    # Mapping instrument info
    info['time']           = defs.now_utc()[4]                # Time of last instrument update
    info['symbol']         = instrument['instId']             # Symbol
    info['baseCoin']       = instrument['baseCcy']            # Base asset, in case of BTCUSDT it is BTC 
    info['quoteCoin']      = instrument['quoteCcy']           # Quote asset, in case of BTCUSDT it is USDT
    info['status']         = instrument['state']              # Is the symbol actively trading?
    info['basePrecision']  = float(instrument['lotSz'])       # Decimal precision of base asset (BTC)
    info['quotePrecision'] = float(instrument['tickSz'])      # Decimal precision of quote asset (USDT)
    info['minOrderQty']    = float(instrument['minSz'])       # Minimum order quantity in base asset (BTC)
    info['tickSize']       = float(instrument['tickSz'])      # Smallest possible price increment of base asset (USDT)
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decoded instrument info:")
        pprint.pprint(info)
        print()
    
    # Return info
    return info

# Decode fee rates
def fees(info, response):
    
    # Debug
    debug = False
    
    # Initialize variables
    rates = response['data'][0]

    # Debug
    if debug:
        defs.announce(f"Debug: Before decode fee rates:")
        pprint.pprint(response)
        print()
    
    # Mapping fee rates
    info['feeMaker'] = abs(float(rates['maker']))   # Maker fee
    info['feeTaker'] = abs(float(rates['taker']))   # Taker fee
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decoded fee rates:")
        print(f"feeMaker: {info['feeMaker']}")
        print(f"feeTaker: {info['feeTaker']}")
    
    # Return info
    return info

# Decode order
def order(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    order = {}
    data  = response['data'][0]
    
    # Debug
    if debug:
        defs.announce(f"Debug: Before decode order:")
        pprint.pprint(response)
        print()

    # Mapping order
    order['createdTime']   = int(data['cTime'])                           # Creation timestamp in ms
    order['updatedTime']   = int(data['uTime'])                           # Last update timestamp in ms
    order['orderid']       = data['algoId']                               # Order ID by exchange
    order['linkedid']      = data['ordId']                                # Linked SL order ID
    order['symbol']        = data['instId']                               # Symbol
    order['side']          = data['side'].capitalize()                    # Buy or Sell
    order['orderType']     = data['ordType'].capitalize()                 # Order type: Market, Limit, etc...
    order['orderStatus']   = data['state'].capitalize()                   # Order state: Live, Pause, Partially_effective, Effective, Canceled, Order_failed, Partially_failed
    order['qty']           = float(data.get('sz'))                        # Quantity in base (BTC)
    order['triggerPrice']  = float(data.get('slTriggerPx'))               # Trigger price in quote (USDT)
    order['avgPrice']      = 0                                            # Average fill price in quote (USDT)
    order['cumExecQty']    = 0                                            # Cumulative executed quantity in base (BTC)
    order['cumExecValue']  = 0                                            # Cumulative executed value in quote (USDT)
    order['cumExecFee']    = 0                                            # Cumulative executed fee in base for buy (BTC) and quote for sell (USDT)
    order['cumExecFeeCcy'] = ''                                           # Cumulative executed fee currency 
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decoded order:")
        pprint.pprint(order)
        print()
    
    # Return order
    return order
    
# Decode linked order to get fills
def linked_order(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    fills = {}
    data  = response['data'][0]

    # Debug
    if debug:
        defs.announce(f"Debug: Before decode fills from linked order:")
        pprint.pprint(response)
        print()
    
    # Mapping fills from linked order
    fills['orderStatus']   = data['state'].capitalize()                   # Order state: Canceled, Live, Partially_filled, Filled and Mmp_canceled
    fills['avgPrice']      = float(data['avgPx'])                         # Average fill price in quote (USDT)
    fills['cumExecQty']    = float(data['accFillSz'])                     # Cumulative executed quantity in base (BTC)
    fills['cumExecValue']  = fills['avgPrice'] * fills['cumExecQty']      # Cumulative executed value in quote (USDT)
    fills['cumExecFee']    = float(data['fee']) * -1                      # Cumulative executed fee in base for buy (BTC) and quote for sell (USDT)
    fills['cumExecFeeCcy'] = data['feeCcy']                               # Cumulative executed fee currency (quote or base, USDT or BTC)
        
    # Debug
    if debug:
        defs.announce(f"Debug: Afer decode fills from linked order:")
        pprint.pprint(fills)
        print()
    
    # Return fills
    return fills
    
# Decode balance
def balance(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    balance = 0

    # Debug
    if debug:
        defs.announce(f"Debug: Before decode balance:")
        pprint.pprint(response)
        print()
    
    # Mapping balance
    try:
        details = response.get("data", [])[0].get("details", [])
        if details and "eq" in details[0]:
            balance = float(details[0].get("eq") or 0)
    except (IndexError, ValueError, TypeError):
        pass  
    
    # Debug
    if debug:
        defs.announce(f"Debug: After decode balance: {balance}")
    
    # Return balance
    return balance

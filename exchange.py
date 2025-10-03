### Sunflow Cryptobot ###
#
# Market data from exchange

# Load external libraries
from loader import load_config
import pprint, time

# Load internal libraries
import defs, okx

# Load config
config = load_config()

# Connect exchange
import okx.Trade as Trade
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.Account as Account
marketDataAPI = MarketData.MarketAPI(flag=config.api_env)
publicDataAPI = PublicData.PublicAPI(flag=config.api_env)
tradeAPI      = Trade.TradeAPI(config.api_key, config.api_secret, config.api_passphrase, False, config.api_env, config.api_site)
accountAPI    = Account.AccountAPI(config.api_key, config.api_secret, config.api_passphrase, False, config.api_env, config.api_site)

# Check the response of a request
def check_response(response, silent=False):
    
    # Debug
    debug = False
    
    # Initialize variables
    code        = 0
    msg         = ""
    sCode       = 0
    sMsg        = ""
    error       = False
    error_code  = 0
    error_msg   = ""
    
    if debug:
        defs.announce(f"Raw response: {response}")

    # Get code and message of request
    try:
        code = int(response['code'])
        msg  = str(response['msg'])
    except KeyError:
        error = True

    # Get rejection or success message of event
    data = response.get("data", [])
    if data:
        first = data[0]
        if isinstance(first, dict) and "sCode" in first:
            sCode = int(first["sCode"])
            sMsg  = str(first.get("sMsg", ""))
    
    # Check if the request message was valid
    if error:
        message = "**** Error: Response of exchange request malformed ***"
        defs.log_error(message)   
   
    # Set error_code and error_msg
    error_code = code
    error_msg  = msg
    if sCode !=0:
        error_code = sCode
        error_msg  = sMsg
    
    # Debug to stdout
    if debug:
        defs.announce("Response codes and messages:")
        print(f"code: {code}", f"\nmsg: {msg}", f"\nsCode: {sCode}", f"\nsMsg: {sMsg}", f"\nerror_code: {error_code}", f"\nerror_msg: {error_msg}\n")

    # Return
    return code, msg, sCode, sMsg, error_code, error_msg

# Deal with API rate limit
def check_limit(code, sCode):
      
    # Debug
    debug = False

    # Initialize variables
    rate_limit = False

    # Debug to stdout
    if debug:
        defs.announce("Debug: Checking exchange response for rate limit issues")
    
    # Initialize variables
    delay       = 5
    limit_codes = (50011, 50013, 51113, 58102)
    
    # Check for rate issues
    if (code in limit_codes) or (sCode in limit_codes):
        rate_limit = True
        defs.log_error(f"*** Warning: API RATE LIMIT HIT, DELAYING SUNFLOW {delay} SECONDS! ***")        
        time.sleep(delay)
    
    # Return cleaned response
    return rate_limit

# Get ticker
def get_ticker():

    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False

    # Get response
    for attempt in range(3):
        message = defs.announce(f"session: marketDataAPI.get_ticker()")
        try:
            response = marketDataAPI.get_ticker(
                instId = config.symbol
            )
        except Exception as e:
            message = f"*** Error: Failed to get ticker ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange result:")
        pprint.pprint(response)
        print()

    # Return result
    return response, error_code, error_msg

# Get klines
def get_klines(interval, limit):

    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False    

    # Get response
    for attempt in range(3):
        message = defs.announce("session: marketDataAPI.get_candlesticks()")
        try:
            response = marketDataAPI.get_candlesticks(
                instId = config.symbol,
                bar    = interval,
                limit  = limit
            )
        except Exception as e:
            message = f"*** Error: Failed to get klines ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get info
def get_instruments():
    
    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False    

    # Get reponse
    for attempt in range(3):
        message = defs.announce("session: publicDataAPI.get_instruments()")
        try:
            response = publicDataAPI.get_instruments(
                instType = "SPOT",
                instId   = config.symbol
            )
        except Exception as e:
            message = f"*** Error: Failed to get info from instrument ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get fee rates
def get_fees():

    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False    

    # Get response
    for attempt in range(3):
        message = defs.announce("session: accountAPI.get_fee_rates()")
        try:
            response = accountAPI.get_fee_rates(
                instType = "SPOT",
                instId   = config.symbol
            )
        except Exception as e:
            message = f"*** Error: Failed to get fee rates from instrument ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]
        
        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break      
       
    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get balance
def get_balance(currency):
    
    # Debug
    debug = False
    
    # Initialize variables
    response    = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False

    # Get reponse
    for attempt in range(3):    
        message = defs.announce("session: accountAPI.get_account_balance()")
        try:
            response = accountAPI.get_account_balance(
                ccy = currency
            )
        except Exception as e:
            message = f"*** Error: Failed to get balance for {currency} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Post order
def place_order(active_order):

    # Debug
    debug = False
    
    # Initialize variables
    kwargs     = {}
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False    

    if debug:
        defs.announce(f"Trying to place {active_order['side']} algo order")
        print(f"instId      = {config.symbol}")
        print(f"tdMode      = cash")
        print(f"side        = {active_order['side'].lower()}")
        print(f"ordType     = conditional")
        print(f"sz          = {str(active_order['qty'])}")
        print(f"tgtCcy      = base_ccy")
        print(f"slTriggerPx = {str(active_order['trigger'])}")
        print(f"slOrdPx     = -1\n")

    # Get response
    for attempt in range(3):
        message = defs.announce("session: tradeAPI.place_algo_order()")
        try:
            kwargs = {
                "instId":      config.symbol,
                "tdMode":      "cash",
                "side":        active_order['side'].lower(),
                "ordType":     "conditional",
                "sz":          str(active_order['qty']),
                "slTriggerPx": str(active_order['trigger']),
                "slOrdPx":     "-1"
            }

            if active_order['side'] == "Buy":
                kwargs["tgtCcy"] = "base_ccy"

            response = tradeAPI.place_algo_order(**kwargs)
            
        except Exception as e:
            message    = f"*** Error: Failed to place {active_order['side']} order ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get order
def get_order(orderid):

    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False
    recheck    = False

    # Get reponse
    if debug: defs.announce(f"Trying to get details for order {orderid}")	
    for attempt in range(10):
        
        # Set checks
        rate_limit = False
        recheck    = False
        
        # Query exchange
        message = defs.announce("session: tradeAPI.get_algo_order_details()")
        try:
            response = tradeAPI.get_algo_order_details(
                algoId = str(orderid)
            )
        except Exception as e:
            message = f"*** Error: Failed to get details on order {orderid} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result = check_response(response, True)
        error_code = result[4]
        error_msg  = result[5]

        # Check if order does not yet exist, it's sometimes delayed
        if error_code == 51603: 
            recheck = True
            defs.announce(f"Rechecking get_order(), maybe it's delayed, attempt {attempt + 1} / 10")
            time.sleep(1 + attempt)
       
        # Check API rate limit, if hit then True
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if (not rate_limit) and (not recheck): break

	# Announce success
    if not rate_limit and not recheck:
        if debug: defs.announce(f"Received details for order {orderid}")
    else:
        defs.log_error(f"*** Warning: Failed to receive details for order {orderid} ***")

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get order
def get_linked_order(linkedid):

    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False
    recheck    = False

    # Get reponse
    if debug: defs.announce(f"Trying to get all fills on linked order {linkedid}")	
    for attempt in range(10):
        
        # Set checks
        rate_limit = False
        recheck    = False
        
        # Query exchange
        message = defs.announce("session: tradeAPI.get_order()")
        try:
            response = tradeAPI.get_order(
                instId = config.symbol,
                ordId  = str(linkedid)
            )
        except Exception as e:
            message = f"*** Error: Failed to get all fills on linked order {linkedid} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result = check_response(response, True)
        error_code = result[4]
        error_msg  = result[5]

        # Check if order is already filled, it's sometimes delayed
        if (response['code'] != '0') and (response['data'][0]['state'] != 'filled'):
            recheck = True
            defs.announce(f"Rechecking get_linked_order(), maybe it's delayed, attempt {attempt + 1} / 10")
            time.sleep(1 + attempt)
       
        # Check API rate limit, if hit then True
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if (not rate_limit) and (not recheck): break

	# Announce success
    if not rate_limit and not recheck:
        if debug: defs.announce(f"Received all fills for linked order {linkedid}")
    else:
        defs.log_error(f"*** Warning: Failed to receive all fills for linked order {linkedid} ***")

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Get fills
def get_fills(orderid):

    # Debug
    debug = False
    
    # Initialize variables
    response    = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False
    recheck    = False

    # Get reponse
    if debug: defs.announce(f"Trying to get fills for order {orderid}")
    for attempt in range(5):
        
        # Set checks
        rate_limit = False
        recheck    = False
        
        # Query exchange
        message = defs.announce("session: tradeAPI.get_fills()")
        try:
            response = tradeAPI.get_fills(
                instType = "SPOT",
                ordId    = orderid,
            )
        except Exception as e:
            message = f"*** Error: Failed to get fills for order {orderid} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result = check_response(response, True)
        error_code = result[4]
        error_msg  = result[5]

        # Check if fills are already present, they're sometimes delayed
        if (response['code'] == '0') and (response['data'] == []): 
            recheck = True
            defs.announce(f"Rechecking get_fills(), maybe they're delayed, attempt {attempt + 1} / 5")
            time.sleep(1)

        # Check API rate limit, if hit then True
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if (not rate_limit) and (not recheck): break

	# Announce success
    if not rate_limit and not recheck:
        if debug: defs.announce(f"Received fills for order {orderid}")
    else:
        defs.log_error(f"*** Warning: Failed to receive fills for order {orderid} ***")

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Cancel order, WARNING WORKAROUND SINCE CANCEL_ALGO_ORDER DOES NOT WORK!
def cancel_order(orderid):
    
    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False

    # Get reponse
    for attempt in range(3):
        message = defs.announce("session: tradeAPI.amend_algo_order()")
        try:
            response = tradeAPI.amend_algo_order(
                instId         = config.symbol,
                algoId         = str(orderid),
                newSlTriggerPx = '0',
                cxlOnFail      = True
            )
        except Exception as e:
            message = f"*** Error: Failed to cancel order {orderid} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # WORKAROUND FOR BROKEN CANCEL_ALGO_ORDERS
        if error_code in (51527, 51543):
            error_code = 0
            error_msg  = ""

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

# Amend order
def amend_order(orderid, new_price=0, new_qty=0):
    
    # Debug
    debug = False
    
    # Initialize variables
    response   = {}
    error_code = 0
    error_msg  = ""
    rate_limit = False

    # Check pre-conditions
    if new_price !=0 and new_qty !=0:
        message = "*** Error: New price and new quantity can't have both values, one must be zero. ***"
        defs.log_error(message)
        return response, error_code, error_msg
    
    # Get reponse
    for attempt in range(3):
        message = defs.announce("session: tradeAPI.amend_algo_order()")
        try:

            if new_price !=0:
                response = tradeAPI.amend_algo_order(
                    instId = config.symbol,
                    algoId = str(orderid),
                    newSlTriggerPx = str(new_price)
                )

            if new_qty !=0:
                response = tradeAPI.amend_algo_order(
                    instId = config.symbol,
                    algoId = str(orderid),
                    newSz  = str(new_qty)
                )

        except Exception as e:
            message = f"*** Error: Failed to amend order {orderid} ***\n>>> Message: {e}"
            defs.log_error(message)

        # Log response
        if config.exchange_log:
            defs.log_exchange(response, message)

        # Check response for errors
        result     = check_response(response)
        error_code = result[4]
        error_msg  = result[5]

        # Check API rate limit
        rate_limit = check_limit(result[0], result[2])
        
        # Break out of loop
        if not rate_limit: break

    # Debug to stdout
    if debug:
        defs.announce("Debug: Exchange response:")
        pprint.pprint(response)
        print()

    # Return data
    return response, error_code, error_msg

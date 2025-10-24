### Sunflow Cryptobot ###
#
# Calculate trigger price distance

# Load external libraries
import math, pandas as pd, pandas_ta as ta

# Load internal libraries
from loader import load_config
import defs, preload

# Load config
config = load_config()

# Initialize ATR timer
atr_timer             = {}
atr_timer['check']    = False
atr_timer['time']     = 0
atr_timer['interval'] = 60000

# Initialize ATR Klines
atr_klines = {'time': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'turnover': []}

# Calculate ATR as percentage
def calculate_atr():
    
    # Debug
    debug = False

    # Declare ATR timer and klines variables global
    global atr_timer, atr_klines

    # Initialize variables
    get_atr_klines = False

    # Check every interval
    current_time = defs.now_utc()[4]
    if atr_timer['check']:
        atr_timer['check'] = False
        atr_timer['time']  = current_time
    if current_time - atr_timer['time'] > atr_timer['interval']:
        defs.announce(f"Requesting {config.prices_limit} klines for ATR")
        atr_timer['check'] = True
        atr_timer['time']  = 0
        get_atr_klines = True

    # Get ATR klines if required
    if get_atr_klines:
        start_time = defs.now_utc()[4]
        atr_klines = preload.get_klines('1m', config.prices_limit)
        end_time   = defs.now_utc()[4]
        defs.announce(f"Received {config.prices_limit} ATR klines in {end_time - start_time}ms")
    
    # Initialize dataframe
    df = pd.DataFrame(atr_klines)
    
    # Calculate ATR and ATR percentage
    start_time     = defs.now_utc()[4]
    df['ATR']      = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ATRP']     = (df['ATR'] / df['close']) * 100
    atr_percentage = df['ATRP'].iloc[-1]
    atr_perc_avg   = df['ATRP'].mean()
    atr_multiplier = atr_percentage / atr_perc_avg
    end_time       = defs.now_utc()[4]

    # Report ATR data
    if get_atr_klines:
        print("ATR Data (experimental)")
        print(f"ATR current percentage is {atr_percentage} %")
        print(f"ATR average percentage over {config.prices_limit} klines is {atr_perc_avg} %")
        print(f"ATR multiplier is {atr_multiplier}\n")

   # Debug to stdout
    if debug:
        defs.announce(f"Debug: ATR percentage is {atr_percentage} %, on average it was {atr_perc_avg} %, the multiplier is {atr_multiplier} and it took {end_time - start_time}ms to calculate")
      
    # Return ATR as percentage
    return atr_percentage, atr_perc_avg, atr_multiplier

# Protect buy and sell
def protect(active_order, price_distance):

    # Debug
    debug = False

    # Initialize variables
    side        = active_order['side']        # Buy or Sell
    default     = active_order['distance']    # Default distance
    wave        = active_order['wave']        # Wave distance
    #fluctuation = active_order['fluctuation']        # Wave distance

    # Direction normalization
    if side == "Buy":
        price_distance *= -1
        wave           *= -1
    
    # Set the fluctuation to wave so it gets the calculated value immediately
    fluctuation = wave

    # Debug to stdout
    if debug:
        defs.announce("Debug: Distances before")
        print(f"Side                : {side}")
        print(f"Default distance    : {default:.4f} %")
        print(f"Price distance      : {price_distance:.4f} %")
        print(f"Wave distance       : {wave:.4f} %")
        print(f"Final fluctuation   : {fluctuation:.4f} %\n")

    # Optional: Enforce a minimum distance
    if config.protect_minimum:
        if fluctuation < default:
            fluctuation = default
    
    # Optional: Once price distance is beyond default, allow to use smaller values
    if config.protect_peaks:
        if (fluctuation < default) and (price_distance > default):
            fluctuation = wave

    # Prevent stop from moving beyond the profitable zone
    if side == "Sell":
        profitable = price_distance + default
        if fluctuation > profitable:
            fluctuation = profitable

    # Safety checks
    if (fluctuation < 0) or (math.isnan(fluctuation)) or (math.isinf(fluctuation)):
        defs.announce(f"*** Warning: Fluctuation distance is {fluctuation:.4f} %, enforcing 0.0000 %! ***")
        fluctuation = 0

    # Set fluctuation
    active_order['fluctuation'] = fluctuation

    # Debug to stdout
    if debug:
        defs.announce("Debug: Distances after")
        print(f"Side                : {side}")
        print(f"Default distance    : {default:.4f} %")
        print(f"Price distance      : {price_distance:.4f} %")
        print(f"Wave distance       : {wave:.4f} %")
        print(f"Final fluctuation   : {fluctuation:.4f} %\n")

    # Return active_order
    return active_order

# Adaptive protection logic that dynamically adjusts trailing distance based on side, regime, ATR, wave strength, and EMA stability.
def protect_respect(active_order, price_distance):

    # Initialize variables
    side        = active_order['side']
    base_dist   = active_order['distance']
    wave        = active_order.get('wave', 0)
    regime      = active_order.get('regime', 'Calm')
    fluctuation = active_order.get('fluctuation', wave)
    price_diff  = price_distance

    # Normalize for Buy side
    if side == "Buy":
        price_diff *= -1
        wave       *= -1
        fluctuation = wave

    # --- 1. Regime-based safety factor ---
    # Trending: looser trailing, Ranging: tighter trailing
    safety_factors = {
        "Trending": 0.85,  # allow trailing further from profit
        "Ranging": 1.2,    # tighten trailing to protect gains
        "Calm": 1.0        # neutral
    }
    safety = safety_factors.get(regime, 1.0)

    # --- 2. Ensure minimum distance ---
    fluctuation = max(fluctuation, base_dist)

    # --- 3. Allow smaller fluctuation if price exceeded default distance (protect peaks) ---
    if config.protect_peaks:
        if (fluctuation < base_dist) and (price_diff > base_dist):
            fluctuation = wave

    # --- 4. Ensure not exceeding profitable zone ---
    if side == "Sell":
        profitable_max = price_diff + base_dist
        if fluctuation > profitable_max * safety:
            fluctuation = profitable_max * safety
    elif side == "Buy":
        profitable_max = price_diff + base_dist
        if fluctuation > profitable_max * safety:
            fluctuation = profitable_max * safety

    # --- 5. Safety checks ---
    if fluctuation < 0 or math.isnan(fluctuation) or math.isinf(fluctuation):
        defs.announce(f"*** Warning: Fluctuation distance invalid ({fluctuation:.4f}%), enforcing 0.0000%! ***")
        fluctuation = 0

    # --- 6. Assign final fluctuation ---
    active_order['fluctuation'] = fluctuation

    return active_order

# Calculate distance using fixed
def distance_fixed(active_order):
    
    # Distance
    active_order['fluctuation'] = active_order['distance']
        
    # Return active_order
    return active_order

# Calculate distance using spot
def distance_spot(active_order, price_distance):
    
    # Reverse fluc_price_distance based on buy or sell
    if active_order['side'] == "Sell":
        fluc_price_distance = price_distance
        if price_distance < 0:
            fluc_price_distance = 0
    else:
        fluc_price_distance = price_distance * -1
        if price_distance > 0:
            fluc_price_distance = 0               

    # Calculate trigger price distance percentage
    fluctuation = (1 / math.pow(10, 1/1.2)) * math.pow(fluc_price_distance, 1/1.2) + active_order['distance']

    # Set fluctuation
    if fluctuation < active_order['distance']:
        active_order['fluctuation'] = active_order['distance']
    else:
        active_order['fluctuation'] = fluctuation

    # Return active_order
    return active_order

# Calculate distance using EMA
def distance_ema(active_order, prices, price_distance):
    
    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 1
    
    # Number of prices to use
    number = defs.get_index_number(prices, config.timeframe, config.prices_limit)

    # Convert the lists to a pandas DataFrame
    df = pd.DataFrame({
        'price': prices['price'],
        'time': pd.to_datetime(prices['time'], unit='ms')
    })
    
    # Set time as the index
    df.set_index('time', inplace=True)
        
    # Calculate the periodic returns
    df['returns'] = df['price'].pct_change()
    
    # Apply an exponentially weighted moving standard deviation to the returns
    df['ewm_std'] = df['returns'].ewm(span=number, adjust=False).std()
    
    # Normalize the last value of EWM_Std to a 0-1 scale
    wave = df['ewm_std'].iloc[-1] / df['ewm_std'].max()
    
    # Calculate trigger price distance percentage
    active_order['wave'] = (wave / scaler)
    
    # Check for failures
    if math.isnan(active_order['wave']):
        active_order['wave'] = active_order['distance']
    
    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using hybrid
def distance_hybrid(active_order, prices, price_distance):

    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 2

    # Number of prices to use
    number = defs.get_index_number(prices, config.wave_timeframe, config.prices_limit)
    
    # Adaptive EMA span based on volatility
    recent_prices = pd.Series(prices['price'][-number:])      # Get recent prices
    volatility = recent_prices.std() / recent_prices.mean()   # Calculate volatility as a percentage
    if math.isnan(volatility): volatility = 0                 # Safeguard volatilty
    ema_span = max(5, int(number * (1 + volatility)))         # Adjust span based on volatility, minimum span of 5

    # Convert the list to a pandas DataFrame
    df = pd.DataFrame(prices['price'], columns=['price'])

    # Calculate the periodic returns
    df['returns'] = df['price'].pct_change()

    # Apply an exponentially weighted moving standard deviation to the returns
    df['ewm_std'] = df['returns'].ewm(span=ema_span, adjust=False).std()

    # Normalize the last value of EWM_Std to a 0-1 scale
    wave = df['ewm_std'].iloc[-1] / df['ewm_std'].max()

    # Calculate dynamic scaler based on market conditions (here we just use the default scaler, but it could be dynamic)
    dynamic_scaler = scaler

    # Calculate trigger price distance percentage
    active_order['wave'] = (wave / dynamic_scaler) + active_order['distance']

    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using wave
def distance_wave(active_order, prices, price_distance, prevent=True):
    
    # Debug
    debug = False

    # Time calculations
    latest_time = prices['time'][-1]                # Get the latest time
    span = latest_time - config.wave_timeframe      # timeframe in milliseconds

    # Get the closest index in the time {timeframe}
    closest_index = defs.get_closest_index(prices, span)

    # Calculate the change in price
    price_change      = 0
    price_change_perc = 0
    if closest_index is not None and prices['time'][-1] > span:
        price_change      = prices['price'][-1] - prices['price'][closest_index]
        price_change_perc = (price_change / prices['price'][closest_index]) * 100

    # Apply wave multiplier
    active_order['wave'] = price_change_perc * config.wave_multiplier

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Price change in the last {config.wave_timeframe / 1000:.2f} seconds is {active_order['wave']:.2f} %")

    # Prevent sell at loss and other issues
    if prevent:
        active_order = protect(active_order, price_distance)

    # Return active_order
    return active_order   

# Calculate distance using wave taking ATR into account
def distance_atr(active_order, prices, price_distance):

    # Initialize variables
    scaler = 1
    result = ()
    
    # Get ATR percentage and average
    result         = calculate_atr()
    atr_percentage = result[0]
    atr_perc_avg   = result[1]
    atr_multiplier = result[2] * scaler

    # Get wave
    active_order = distance_wave(active_order, prices, price_distance, False)

    # Adjust active_order
    active_order['wave'] = atr_multiplier * active_order['wave']

    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate trigger distance dynamically using ATR + EMA + Wave
def distance_adaptive(active_order, prices, price_distance):

    # Get ATR metrics
    atr_percentage, atr_avg, atr_mult = calculate_atr()

    # Wave Strength
    wave_order    = distance_wave(active_order.copy(), prices, price_distance, prevent=False)
    wave_strength = abs(wave_order['wave'])

    # EMA Stability
    df = pd.DataFrame({
        'price': prices['price'],
        'time': pd.to_datetime(prices['time'], unit='ms')
    })
    df.set_index('time', inplace=True)
    df['returns'] = df['price'].pct_change()
    df['ewm_std'] = df['returns'].ewm(span=14, adjust=False).std()
    ema_stability = 1 - (df['ewm_std'].iloc[-1] / df['ewm_std'].max())  # closer to 1 = stable trend

    # Combine Signals
    # ATR increases distance when volatility is high
    # Wave increases distance during strong movements
    # EMA stability reduces distance during smooth trends
    adaptive_scaler = 1.0 + (atr_mult * 0.5) + (wave_strength * 0.3) - (ema_stability * 0.2)

    # Compute the adaptive trigger distance
    adaptive_distance = active_order['distance'] * adaptive_scaler

    # Ensure minimum distance
    if adaptive_distance < active_order['distance']:
        adaptive_distance = active_order['distance']

    # Adjust active_order
    active_order['wave']        = wave_strength
    active_order['fluctuation'] = adaptive_distance
    
    # Prevent sell at loss and other issues    
    active_order = protect_respect(active_order, price_distance)

    # Return active_order
    return active_order

# Smart trigger distance calculator combining ATR, Wave, and EMA stability with adaptive regime detection (trending vs. ranging)
def distance_smart(active_order, prices, price_distance):

    # === 1. Get ATR data ===
    atr_percentage, atr_avg, atr_mult = calculate_atr()

    # === 2. Wave detection (short-term momentum) ===
    wave_order    = distance_wave(active_order.copy(), prices, price_distance, prevent=False)
    wave_strength = abs(wave_order['wave'])  # magnitude of short-term movement

    # === 3. EMA-based trend stability ===
    df = pd.DataFrame({
        'price': prices['price'],
        'time': pd.to_datetime(prices['time'], unit='ms')
    })
    df.set_index('time', inplace=True)
    df['returns'] = df['price'].pct_change()
    df['ema'] = df['price'].ewm(span=14, adjust=False).mean()
    df['ema_slope'] = df['ema'].diff()

    # EMA volatility and slope metrics
    df['ewm_std'] = df['returns'].ewm(span=14, adjust=False).std()
    ema_stability = 1 - (df['ewm_std'].iloc[-1] / df['ewm_std'].max())  # 1=stable, 0=chaotic
    ema_slope = df['ema_slope'].iloc[-1] / df['ema'].iloc[-1] if df['ema'].iloc[-1] != 0 else 0

    # === 4. Regime Detection ===
    # If volatility and slope are both high → trending
    # If volatility is high but slope is flat → ranging
    trend_strength = abs(ema_slope) * 1000  # normalized slope in %
    vol_ratio = atr_percentage / max(atr_avg, 1e-9)  # volatility relative to baseline

    if trend_strength > 0.05 and vol_ratio > 1.1:
        regime = "Trending"
    elif vol_ratio > 1.2 and trend_strength < 0.03:
        regime = "Ranging"
    else:
        regime = "Calm"

    # === 5. Adaptive weighting based on regime ===
    if regime == "Trending":
        w_atr, w_wave, w_stab = 0.4, 0.4, 0.2
    elif regime == "Ranging":
        w_atr, w_wave, w_stab = 0.5, 0.2, 0.3
    else:  # Calm
        w_atr, w_wave, w_stab = 0.3, 0.2, 0.5

    # === 6. Composite adaptive multiplier ===
    adaptive_mult = (
        (atr_mult * w_atr) +            # volatility component
        (wave_strength * w_wave) +      # recent momentum component
        ((1 - ema_stability) * w_stab)  # trend stability inverse (more chaos → more distance)
    )

    # === 7. Final distance computation ===
    base_distance = active_order['distance']
    adaptive_distance = base_distance * (1 + adaptive_mult)

    # Enforce reasonable limits
    adaptive_distance = max(base_distance * 0.8, min(adaptive_distance, base_distance * 3))

    # === 8. Assign results ===
    active_order['wave']        = wave_strength
    active_order['fluctuation'] = adaptive_distance
    active_order['regime']      = regime
    
    # === 9. Apply protection logic ===
    active_order = protect_respect(active_order, price_distance)

    # === 10. Optional debug ===
    defs.announce(f"[{regime}] distance={adaptive_distance:.4f}% | ATRx={atr_mult:.2f} | Wave={wave_strength:.2f} | Stability={ema_stability:.2f}")

    return active_order

# Calculate trigger price distance
def calculate(active_order, prices):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Store previous fluctuation
    previous_fluctuation = active_order['fluctuation']
    
    # By default fluctuation equals distance
    active_order['fluctuation'] = active_order['distance']
    
    # Calculate price distance since start of trailing in percentages 
    price_distance = ((active_order['current'] - active_order['start']) / active_order['start']) * 100

    ''' Use FIXED to set trigger price distance '''
    if active_order['wiggle'] == "Fixed":
        active_order = distance_fixed(active_order)

    ''' Use SPOT to set trigger price distance '''
    if active_order['wiggle'] == "Spot":
        active_order = distance_spot(active_order, price_distance)

    ''' Use WAVE to set distance '''
    if active_order['wiggle'] == "Wave":
        active_order = distance_wave(active_order, prices, price_distance)

    ''' Use ATR for WAVE to set distance '''
    if active_order['wiggle'] == "ATR":
        active_order = distance_atr(active_order, prices, price_distance)

    ''' Use EMA to set trigger price distance '''
    if active_order['wiggle'] == "EMA":
        active_order = distance_ema(active_order, prices, price_distance)

    ''' Use HYBRID to set distance '''
    if active_order['wiggle'] == "Hybrid":
        active_order = distance_hybrid(active_order, prices, price_distance)

    ''' Use ADAPATIVE to set distance '''
    if active_order['wiggle'] == "Adaptive":
        active_order = distance_adaptive(active_order, prices, price_distance)

    ''' Use SMART to set distance '''
    if active_order['wiggle'] == "Smart":
        active_order = distance_smart(active_order, prices, price_distance)

    # Report to stdout
    if previous_fluctuation != active_order['fluctuation']:
        defs.announce(f"Adviced trigger price distance is now {active_order['fluctuation']:.4f} %")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return modified data
    return active_order

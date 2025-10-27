### Sunflow Cryptobot ###
#
# Calculate trigger price distance

# Load external libraries
import numpy as np
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
        defs.announce(f"Requesting {config.limit} klines for ATR")
        atr_timer['check'] = True
        atr_timer['time']  = 0
        get_atr_klines = True

    # Get ATR klines if required
    if get_atr_klines:
        start_time = defs.now_utc()[4]
        atr_klines = preload.get_klines('1m', config.limit)
        end_time   = defs.now_utc()[4]
        defs.announce(f"Received {config.limit} ATR klines in {end_time - start_time}ms")
    
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
        print(f"ATR average percentage over {config.limit} klines is {atr_perc_avg} %")
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
    fluctuation = active_order['wave']        # Trigger price distance

    # Direction normalization
    if side == "Buy":
        price_distance *= -1
        wave           *= -1
    
    # Debug to stdout
    if debug:
        defs.announce("Debug: Distances before")
        print(f"Side                : {side}")
        print(f"Default distance    : {default:.4f} %")
        print(f"Price distance      : {price_distance:.4f} %")
        print(f"Wave distance       : {wave:.4f} %")
        print(f"Final fluctuation   : {fluctuation:.4f} %\n")

    # Optional: Enforce a minimum distance
    if config.wave_minimum:
        if fluctuation < default:
            fluctuation = default
    
    # Optional: Price distance is above default, possibly override the above
    if config.wave_peaks:
        if (fluctuation < default) and (price_distance > default):
            fluctuation = wave        

    # Prevent stop from moving beyond the profitable zone
    if side == "Sell":
        profitable = price_distance + default
        if fluctuation > profitable:
            fluctuation = profitable
    
    # Safety checks
    if (fluctuation is None) or (fluctuation < 0) or (math.isnan(fluctuation)) or (math.isinf(fluctuation)):
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

# Calculate distance using fixed
def distance_fixed(active_order):
    
    # Set fluctuation and wave, no need to go through protect()
    active_order['fluctuation'] = active_order['distance']
    active_order['wave']        = active_order['distance']
        
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

    # Set fluctuation, no need to go through protect()
    if fluctuation < active_order['distance']:
        active_order['fluctuation'] = active_order['distance']
    else:
        active_order['fluctuation'] = fluctuation
        
    # Set wave, to be compatible with the other distance functions
    active_order['wave'] = active_order['fluctuation']
    
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

    # Set wave and apply wave multiplier
    active_order['wave'] = price_change_perc * config.wave_multiplier

    # Debug to stdout
    if debug:
        defs.announce(f"Debug: Price change in the last {config.wave_timeframe / 1000:.2f} seconds is {active_order['wave']:.2f} %")

    # Prevent sell at loss and other issues
    if prevent:
        active_order = protect(active_order, price_distance)

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

# Advanced adaptive distance calculation designed by ChatGPT :)
def distance_chatgpt(active_order, prices, price_distance):
    """
    Highly adaptive trigger distance:
      - Uses ATR (or percent stddev) as volatility baseline
      - Uses EWMA of returns to detect trend strength and direction
      - Computes candidate distances from Fixed/Spot/Wave
      - Dynamically weights candidates based on volatility & trend
      - Adds hysteresis and time-aware smoothing to prevent whipsaw
      - Caps/flattens distances with profit-aware limits and config knobs
    """

    # Debug toggle
    debug = True

    now_ms = defs.now_utc()[4]  # existing helper returns time, index 4 is millis in your codebase
    MIN_HISTORY = 20  # minimal price points to compute meaningful stats

    # Ensure prices arrays exist and have enough length
    price_series = pd.Series(prices.get('price', []))
    time_series  = pd.Series(prices.get('time', []))
    n = len(price_series)

    # Fallback: if not enough history, return safe fixed distance
    if n < MIN_HISTORY:
        if debug: defs.announce("Debug: Insufficient history, falling back to fixed")
        return distance_fixed(active_order)

    # --- 1) Volatility estimates ---
    # 1a. ATR-like (True Range) using simple price diffs (since candles may not be provided)
    # Use percent ATR (so it's comparable to distance %)
    returns = price_series.pct_change().dropna()
    if len(returns) < 2:
        vol_pct = 0.0
    else:
        # EWMA volatility (gives more weight to recent moves)
        span_vol = max(10, min(60, int(config.chatgpt_vol_ewma_span)))
        ewma_var = returns.ewm(span=span_vol, adjust=False).var().iloc[-1]
        vol_pct = (np.sqrt(ewma_var) * 100) if (not np.isnan(ewma_var)) else returns.std() * 100

    # 1b. Simple recent range (high-low proxy from recent window)
    window = min(50, n)
    recent = price_series.iloc[-window:]
    recent_range_pct = ((recent.max() - recent.min()) / recent.min()) * 100 if recent.min() > 0 else 0.0

    # Combine vol measures (clamped)
    volatility = max(vol_pct, recent_range_pct * 0.5)
    volatility = max(volatility, 0.0)  # clamp
    # Normalize volatility to 0..1 (configurable scaling)
    vol_norm = min(volatility / max(1.0, config.chatgpt_vol_scale), 1.0)

    # --- 2) Trend & momentum ---
    # EMA of returns for trend direction/strength
    trend_span = max(5, min(40, int(config.chatgpt_trend_ema_span)))
    ema_ret = returns.ewm(span=trend_span, adjust=False).mean().iloc[-1]
    # trend_strength expressed as percentage magnitude
    trend_strength = abs(ema_ret) * 100
    trend_dir = 1 if ema_ret > 0 else -1 if ema_ret < 0 else 0
    trend_norm = min(trend_strength / max(0.01, config.chatgpt_trend_scale), 1.0)

    # --- 3) Candidate distances (absolute % values) ---
    # Use your existing functions to get candidate distances (we'll take absolute magnitudes for combination)
    # Make copies so they don't mutate original
    try:
        fixed_cand = distance_fixed(active_order.copy())['fluctuation']
        spot_cand  = distance_spot(active_order.copy(), price_distance)['fluctuation']
        wave_cand  = distance_wave(active_order.copy(), prices, price_distance, prevent=False)['fluctuation']
    except Exception:
        # If something fails, fallback to safe fixed distance
        if debug: defs.announce("Debug: candidate calc failed, falling back fixed")
        return distance_fixed(active_order)

    # Convert to positive magnitude to combine — keep sign handling to protect() later
    fixed_mag = abs(float(fixed_cand))
    spot_mag  = abs(float(spot_cand))
    wave_mag  = abs(float(wave_cand))

    # --- 4) Adaptive weighting logic ---
    # Base weights (configurable)
    w_fixed_base = config.chatgpt_w_fixed
    w_wave_base  = config.chatgpt_w_wave
    w_spot_base  = config.chatgpt_w_spot

    # Modulate weights:
    # - When volatility is high, prefer wave+fixed (wider stops)
    # - When trend is strong, increase spot weight (tighter if trend supports)
    weight_spot = w_spot_base + (trend_norm * 0.5) * (1 - vol_norm)  # trend helps spot, but not if very volatile
    weight_wave = w_wave_base + (vol_norm * 0.4)
    weight_fixed = w_fixed_base + (vol_norm * 0.2)

    # Normalize weights
    total_w = weight_fixed + weight_wave + weight_spot
    if total_w <= 0:
        weight_fixed, weight_wave, weight_spot = 0.33, 0.33, 0.34
    else:
        weight_fixed /= total_w
        weight_wave  /= total_w
        weight_spot  /= total_w

    # Compute adaptive magnitude (weighted)
    adaptive_mag = (fixed_mag * weight_fixed) + (wave_mag * weight_wave) + (spot_mag * weight_spot)

    # --- 5) Profit-aware caps and dynamic multipliers ---
    # If active position is already profitable, allow tighter trailing (reduce distance), else be conservative
    current_profit = price_distance  # already in percent (positive or negative depending on side handling)
    # For Sell side, price_distance positive means price went up since start -> profitable for Sell? Keep logic consistent with protect()
    profit_factor = 1.0
    if active_order.get('side') == "Sell":
        if current_profit > 0:
            profit_factor = max(0.6, 1.0 - min(0.6, current_profit / 10.0))  # the more profit, the more we can tighten
    else:  # Buy side
        if current_profit < 0:
            # for buys, negative price_distance -> price dropped vs start (profit for buy only when price is below start?), be conservative
            profit_factor = 1.0

    adaptive_mag *= profit_factor

    # Limiters: don't go below default distance, don't exceed a safe maximum multiplier
    #min_allowed = float(active_order.get('distance', 0.0))
    min_allowed = 0
    max_multiplier = float(config.chatgpt_max_multiplier)
    adaptive_mag = max(adaptive_mag, min_allowed)
    adaptive_mag = min(adaptive_mag, min_allowed * max_multiplier)

    # --- 6) Hysteresis & smoothing to avoid rapid toggles ---
    # Hysteresis threshold (percent change required to actually update)
    start_fluc = float(active_order.get('fluctuation', min_allowed))
    hysteresis_pct = float(config.chatgpt_hysteresis_pct)  # 5% relative change required
    # Compute relative change
    if start_fluc <= 0:
        rel_change = float('inf')
    else:
        rel_change = abs(adaptive_mag - start_fluc) / start_fluc

    # Time-based smoothing: more recent updates allow slightly more rapid change
    # Use EWMA smoothing factor that itself adapts: higher volatility -> slower smoothing
    base_smooth = float(config.chatgpt_smoothing_alpha)
    adaptive_alpha = base_smooth * (1.0 - vol_norm * 0.6)   # if vol high, reduce alpha (slower changes)
    adaptive_alpha = min(max(adaptive_alpha, 0.05), 0.9)

    # If change is small (below hysteresis) keep previous (smaller CPU churn)
    if rel_change < hysteresis_pct:
        # but still apply light EWMA to slowly nudge towards adaptive_mag
        new_fluc = (start_fluc * (1 - adaptive_alpha)) + (adaptive_mag * adaptive_alpha)
    else:
        # large change -> respond quicker but cap how much we can change in single update
        max_step = float(config.chatgpt_max_step_pct)  # max relative step per update
        max_step = max_step if max_step > 0 else 0.5
        allowed = start_fluc * (1 + max_step)
        lower_allowed = start_fluc * (1 - max_step)
        proposed = (start_fluc * (1 - adaptive_alpha)) + (adaptive_mag * adaptive_alpha)
        # clamp
        new_fluc = min(max(proposed, lower_allowed), allowed)

    # --- 7) Direction handling & protect ---
    # The rest of your system expects 'fluctuation' to have sign depending on side (your protect() handles it).
    # We'll set positive magnitude here; protect() will enforce final sign and minimums.
    active_order['wave'] = float(new_fluc)

    # Call protect to enforce business rules (minimums, wave_peaks, profitable zone caps)
    active_order = protect(active_order, price_distance)

    # Final safety assignment
    final = active_order.get('fluctuation', 0.0)

    # --- Debugging output ---
    if debug:
        defs.announce("Debug: ChatGPT data")
        print(f"volatility (pct): {volatility:.4f}")
        print(f"vol_norm        : {vol_norm:.4f}")
        print(f"trend_strength  : {trend_strength:.4f}")
        print(f"trend_norm      : {trend_norm:.4f}, dir {trend_dir}")
        print(f"fixed_mag       : {fixed_mag:.4f}")
        print(f"wave_mag        : {wave_mag:.4f}")
        print(f"spot_mag        : {spot_mag:.4f}")
        print(f"weights         : fixed={weight_fixed:.3f}, wave={weight_wave:.3f}, spot={weight_spot:.3f}")
        print(f"adaptive_mag    : {adaptive_mag:.4f}")
        print(f"start_fluc       : {start_fluc:.4f}, new_fluc {new_fluc:.4f}")
        print(f"final_fluc      : {final:.4f}")

    # Return active_order
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

    ''' Use CHATGPT (adaptive) to dynamically combine Fixed, Spot, and Wave '''
    if active_order['wiggle'] == "ChatGPT":
        active_order = distance_chatgpt(active_order, prices, price_distance)
       
    # Report to stdout
    if previous_fluctuation != active_order['fluctuation']:
        defs.announce(f"Adviced trigger price distance is now {active_order['fluctuation']:.4f} %")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return modified data
    return active_order

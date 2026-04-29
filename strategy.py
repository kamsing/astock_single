import re
import pandas as pd
import numpy as np

def calculate_ma(df_daily, period_type, window, shift=0):
    """
    Calculate Moving Average for D (Daily), W (Weekly), M (Monthly).
    df_daily is the daily dataframe UP TO the current evaluation date T.
    """
    if len(df_daily) == 0:
        return np.nan
        
    df = df_daily.copy()
    df.set_index('日期', inplace=True)
    
    if period_type == 'D':
        # Daily is straightforward
        series = df['收盘']
    elif period_type == 'W':
        # Resample to weekly. We use 'W-FRI' (ending Friday)
        # The last row might be a partial week.
        series = df['收盘'].resample('W-FRI').last()
    elif period_type == 'M':
        # Resample to monthly. 'M' is month end.
        series = df['收盘'].resample('M').last()
    else:
        raise ValueError(f"Unknown period type: {period_type}")
        
    # Calculate MA
    ma_series = series.rolling(window=window).mean()
    
    # Apply shift
    if shift > 0:
        ma_series = ma_series.shift(shift)
        
    # The value we want is the very last one in the series
    if len(ma_series) > 0:
        return ma_series.iloc[-1]
    return np.nan

def parse_and_eval_kline_strategy(strategy_str, df_daily):
    """
    Evaluates a strategy string like ((M5MA > M10MA > M20MA) * 3) && (W10MA > W30MA) || ((D5MA > D10MA) * 2)
    For `* N`, it means the condition was true for N consecutive days including today.
    Wait, to evaluate `* N`, we need to evaluate the condition for the past N days.
    This implies we should vectorize the evaluation over the dataframe.
    """
    # For a robust implementation, we will translate the strategy into a pandas eval expression.
    # First, let's identify all unique MA requirements
    # Pattern: [DWM]\d+MA(?:-\d+)?
    ma_pattern = r'([DWM])(\d+)MA(?:-(\d+))?'
    ma_matches = re.findall(ma_pattern, strategy_str)
    
    # We will compute these MAs for ALL dates in df_daily to allow vectorization.
    # This is much faster.
    df = df_daily.copy()
    df.set_index('日期', inplace=True)
    
    # Prepare base series
    series_d = df['收盘']
    series_w = df['收盘'].resample('W-FRI').last()
    series_m = df['收盘'].resample('M').last()
    
    # Map from resampled index back to daily index (forward fill)
    # Actually, for Weekly and Monthly MAs evaluated on a daily basis:
    # We want the MA calculated up to that day.
    # A vectorized way to do this for Weekly:
    # 1. Calculate daily MA is easy: rolling(N)
    # 2. Weekly MA on day T is the mean of the close of the last N-1 weeks AND the close on day T.
    
    # To keep it simple and accurate based on trading software:
    # Let's write a function that evaluates a basic condition without * N for a specific row index.
    pass # Re-thinking approach below

def parse_condition_for_date(condition_str, df_daily_up_to_T):
    # This evaluates a simple condition without * N, e.g., D5MA > D30MA
    # We will replace D5MA with its value.
    expr = condition_str
    
    ma_pattern = r'([DWM])(\d+)MA(?:-(\d+))?'
    
    # Find all matches, calculate them, and replace in string
    # We use regex substitution
    def replacer(match):
        ptype = match.group(1)
        window = int(match.group(2))
        shift = int(match.group(3)) if match.group(3) else 0
        val = calculate_ma(df_daily_up_to_T, ptype, window, shift)
        return str(val) if not pd.isna(val) else "False" # If NaN, comparison will be tricky, "False" might break, let's use "float('nan')"

    # Replace MAs
    for match in re.finditer(ma_pattern, condition_str):
        full_str = match.group(0)
        ptype = match.group(1)
        window = int(match.group(2))
        shift = int(match.group(3)) if match.group(3) else 0
        val = calculate_ma(df_daily_up_to_T, ptype, window, shift)
        if pd.isna(val):
            expr = expr.replace(full_str, "(-9999999.0)") # Use a very negative number for NaN so comparisons gracefully fail
        else:
            expr = expr.replace(full_str, f"({val})")
            
    # Now replace logical operators
    expr = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
    
    # Chain comparisons like (M5MA > M10MA > M20MA) works natively in Python!
    try:
        return eval(expr)
    except Exception as e:
        # print(f"Eval error on {expr}: {e}")
        return False

def evaluate_kline_strategy_on_date(strategy_str, df_daily, date_idx):
    """
    Evaluates the full strategy on a specific date index.
    date_idx is the index (integer) in df_daily.
    Handles the `* N` syntax.
    """
    # Find all `(...) * N` blocks
    # regex to find something in parentheses followed by * \d+
    # This might be tricky if parentheses are nested. 
    # For simplicity, we assume the pattern is `(...) * N` where `...` has no nested * N
    
    # We will replace `(Cond) * N` with a boolean result.
    
    def replacer(match):
        cond = match.group(1)
        n_days = int(match.group(2))
        
        # Check this condition for date_idx, date_idx-1, ..., date_idx - n_days + 1
        for i in range(n_days):
            check_idx = date_idx - i
            if check_idx < 0:
                return "False" # Not enough days
            
            df_slice = df_daily.iloc[:check_idx + 1]
            res = parse_condition_for_date(cond, df_slice)
            if not res:
                return "False"
        return "True"

    # Pattern: match `( ... ) * N` non-greedily
    # This doesn't handle nested parentheses well if there are multiple. 
    # A robust way is to find `* \d+` and look backwards for the matching parenthesis.
    
    expr = strategy_str
    
    # Quick and dirty parser for `(...) * N`
    while '*' in expr:
        # Find the first '*'
        star_idx = expr.find('*')
        # Find the number after '*'
        match = re.match(r'\s*(\d+)', expr[star_idx+1:])
        if not match:
            break
        n_days = int(match.group(1))
        end_num_idx = star_idx + 1 + match.end()
        
        # Find the preceding parenthesis block
        # We look left from star_idx
        left_str = expr[:star_idx].rstrip()
        if not left_str.endswith(')'):
            break # Invalid syntax
            
        # Find the matching '('
        depth = 0
        match_left_idx = -1
        for i in range(len(left_str)-1, -1, -1):
            if left_str[i] == ')':
                depth += 1
            elif left_str[i] == '(':
                depth -= 1
                if depth == 0:
                    match_left_idx = i
                    break
                    
        if match_left_idx == -1:
            break # Unmatched parentheses
            
        cond_str = left_str[match_left_idx+1 : len(left_str)-1]
        
        # Evaluate `cond_str` for `n_days`
        res = "True"
        for i in range(n_days):
            check_idx = date_idx - i
            if check_idx < 0:
                res = "False"
                break
            df_slice = df_daily.iloc[:check_idx + 1]
            if not parse_condition_for_date(cond_str, df_slice):
                res = "False"
                break
                
        # Replace the whole block in expr
        expr = expr[:match_left_idx] + res + expr[end_num_idx:]

    # Now evaluate the rest of the string which has no `* N`
    df_slice_current = df_daily.iloc[:date_idx + 1]
    final_res = parse_condition_for_date(expr, df_slice_current)
    return bool(final_res)

def evaluate_trade_strategy_buy(buy_rule, df_daily_up_to_T):
    """
    Evaluates if today triggers a buy.
    e.g. DK < -2%
    """
    if len(df_daily_up_to_T) < 2:
        return False
        
    today = df_daily_up_to_T.iloc[-1]
    yesterday = df_daily_up_to_T.iloc[-2]
    
    expr = buy_rule
    
    # DK represents (today.close - yesterday.close) / yesterday.close
    dk = (today['收盘'] - yesterday['收盘']) / yesterday['收盘']
    
    # Replace DK
    expr = expr.replace('DK', str(dk))
    
    # Replace % with /100
    expr = re.sub(r'([-\d.]+)%', lambda m: str(float(m.group(1))/100), expr)
    
    # Other indicators like WK, MK could be added here if needed
    
    try:
        return eval(expr)
    except:
        return False

def evaluate_trade_strategy_sell(sell_rule, buy_price, hold_days, current_price):
    """
    Evaluates if today triggers a sell.
    sell_rule: GAIN=5%, LOSS=10%, PERIOD=60
    """
    rules = [r.strip() for r in sell_rule.split(',')]
    for r in rules:
        if '=' not in r:
            continue
        key, val = r.split('=')
        key = key.strip().upper()
        val = val.strip()
        
        if key == 'GAIN':
            perc = float(val.replace('%', '')) / 100
            if current_price >= buy_price * (1 + perc):
                return True, "止盈"
        elif key == 'LOSS':
            perc = float(val.replace('%', '')) / 100
            if current_price <= buy_price * (1 - perc):
                return True, "止损"
        elif key == 'PERIOD':
            period = int(val)
            if hold_days >= period:
                return True, "到期"
                
    return False, ""

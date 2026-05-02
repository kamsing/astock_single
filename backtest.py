import pandas as pd
from datetime import datetime, timedelta
from data import get_stock_data, prepare_data_for_date
from strategy import evaluate_kline_strategy_on_date, evaluate_trade_strategy_buy, evaluate_trade_strategy_sell

def run_backtest(config):
    stock_codes = config.get("target_stock_code", "000001").split(';')
    save_offline = config.get("save_offline_data", True)
    backtest_year = config.get("backtest_year", 3)
    kline_strategy = config.get("kline_strategy", "")
    trade_strategy = config.get("trade_strategy", {})
    buy_rule = trade_strategy.get("buy_rule", "")
    sell_rule = trade_strategy.get("sell_rule", "")

    all_trades = []
    
    # We will backtest each stock independently
    for stock_code in stock_codes:
        if not stock_code:
            continue
            
        df = get_stock_data(stock_code, save_offline)
        if df.empty:
            continue
            
        # Filter by backtest year
        end_date = pd.to_datetime(datetime.today().date())
        start_date = end_date - timedelta(days=backtest_year * 365)
        
        # If stock listed later than start_date, it naturally uses available data
        df_backtest = df[df['日期'] >= start_date].copy()
        if df_backtest.empty:
            continue
            
        # Initial states
        position = False
        buy_price = 0.0
        buy_date = None
        hold_days = 0
        stock_name = f"Stock_{stock_code}" # akshare daily hist doesn't return name directly, we can just use code
        
        # Start index in the overall df
        start_idx = df_backtest.index[0]
        
        for i in range(start_idx, len(df)):
            current_date = df.loc[i, '日期']
            current_price = df.loc[i, '收盘']
            
            # If we hold position, check sell
            if position:
                hold_days += 1
                sell_flag, sell_reason = evaluate_trade_strategy_sell(
                    sell_rule, buy_price, hold_days, current_price
                )
                
                if sell_flag:
                    # Execute sell
                    profit_amt = (current_price - buy_price) * (1000000 / buy_price) # simulate buying with 100万
                    profit_pct = (current_price - buy_price) / buy_price
                    all_trades.append({
                        "buy_date": buy_date.strftime('%Y-%m-%d'),
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "buy_price": buy_price,
                        "sell_date": current_date.strftime('%Y-%m-%d'),
                        "sell_price": current_price,
                        "profit_amount": profit_amt,
                        "profit_percent": profit_pct,
                        "sell_reason": sell_reason,
                        "hold_days": hold_days
                    })
                    position = False
                    buy_price = 0.0
                    buy_date = None
                    hold_days = 0
            else:
                # Check k-line strategy
                # Since evaluate_kline_strategy_on_date uses data up to i
                is_uptrend = evaluate_kline_strategy_on_date(kline_strategy, df, i)
                
                if is_uptrend:
                    # Check buy strategy
                    df_up_to_now = df.iloc[:i+1]
                    if evaluate_trade_strategy_buy(buy_rule, df_up_to_now):
                        position = True
                        buy_price = current_price
                        buy_date = current_date
                        hold_days = 0
                        
    # Calculate statistics
    df_trades = pd.DataFrame(all_trades)
    
    total_trades = len(df_trades)
    win_rate = 0.0
    roi = 0.0
    avg_hold_days = 0.0
    
    if total_trades > 0:
        win_trades = len(df_trades[df_trades['profit_percent'] > 0])
        win_rate = win_trades / total_trades
        # Assuming we invest 1,000,000 completely each time, no compound interest
        # The prompt says: "以100万为初始交易资金，历史交易投资回报率"
        total_profit = df_trades['profit_amount'].sum()
        roi = total_profit / 1000000.0
        avg_hold_days = df_trades['hold_days'].mean()
        
    stats = {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "roi": roi,
        "avg_hold_days": avg_hold_days
    }
    
    return df_trades, stats

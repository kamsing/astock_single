import os
import pandas as pd
import akshare as ak
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_stock_data(stock_code, save_offline=True):
    """
    Fetch daily k-line data for a given stock code.
    If save_offline is True, it will cache the data locally as CSV.
    """
    file_path = os.path.join(DATA_DIR, f"{stock_code}_daily.csv")
    
    # Check if we should load from local
    if save_offline and os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').reset_index(drop=True)
        
        # Check if it's up to date
        latest_date = df['日期'].iloc[-1]
        today = pd.to_datetime(datetime.today().date())
        # If it's updated within the last few days, we might just use it, 
        # or we could fetch incrementally. For simplicity, we fetch all and overwrite if not today.
        # But markets close at 15:00 and weekends exist. A simple heuristic:
        if (today - latest_date).days < 1:
            return df

    # Fetch from akshare
    print(f"Fetching data for {stock_code} from akshare...")
    try:
        # stock_zh_a_hist requires stock code like 000001
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').reset_index(drop=True)
        
        if save_offline:
            df.to_csv(file_path, index=False)
            
        return df
    except Exception as e:
        print(f"Failed to fetch data for {stock_code}: {e}")
        # fallback to local if exists
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['日期'] = pd.to_datetime(df['日期'])
            return df
        return pd.DataFrame()

def prepare_data_for_date(df_daily, current_date):
    """
    Slice the daily dataframe up to current_date.
    This simulates the data available at the end of current_date.
    """
    return df_daily[df_daily['日期'] <= current_date].copy()

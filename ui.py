import streamlit as st
import pandas as pd
from config import load_config, save_config
from backtest import run_backtest

st.set_page_config(page_title="ASTOCK 股票回测系统", layout="wide", initial_sidebar_state="expanded")

def main():
    st.title("📈 ASTOCK 单支股票量化回测系统")
    st.markdown("基于自定义规则引擎的股票回测工具，支持K线形态和交易策略回测。")

    # Load Config
    config = load_config()

    # Sidebar for Config
    st.sidebar.header("⚙️ 策略配置")
    
    with st.sidebar.form("config_form"):
        target_stock_code = st.text_input("目标股票代码 (多个用分号隔开)", value=config.get("target_stock_code", "000001"))
        backtest_year = st.number_input("回测年数", min_value=1, max_value=20, value=config.get("backtest_year", 3))
        save_offline_data = st.checkbox("本地保存离线数据", value=config.get("save_offline_data", True))
        
        st.subheader("K线策略")
        kline_strategy = st.text_input("K线策略规则", value=config.get("kline_strategy", "(D5MA > D30MA) * 3"))
        st.caption("例: ((M5MA > M10MA > M20MA) * 3) && (W10MA > W30MA) || ((D5MA > D10MA) * 2)")
        
        st.subheader("交易策略")
        trade_strategy = config.get("trade_strategy", {})
        buy_rule = st.text_input("买入规则", value=trade_strategy.get("buy_rule", "DK < -2%"))
        sell_rule = st.text_input("卖出规则", value=trade_strategy.get("sell_rule", "GAIN=5%, LOSS=10%, PERIOD=60"))
        
        submit_button = st.form_submit_button(label="保存配置")
        
    if submit_button:
        new_config = {
            "target_stock_code": target_stock_code,
            "backtest_year": backtest_year,
            "save_offline_data": save_offline_data,
            "kline_strategy": kline_strategy,
            "trade_strategy": {
                "buy_rule": buy_rule,
                "sell_rule": sell_rule
            }
        }
        save_config(new_config)
        st.sidebar.success("配置已保存！")
        config = new_config

    st.divider()

    # Main area
    if st.button("🚀 开始回测", type="primary"):
        with st.spinner('正在获取数据并执行回测，请稍候...'):
            df_trades, stats = run_backtest(config)
            
        if stats["total_trades"] == 0:
            st.warning("回测完成，在此期间未触发任何交易。")
        else:
            st.success("回测完成！")
            
            # Metrics
            st.subheader("📊 回测统计分析")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("历史交易总次数", f'{stats["total_trades"]} 次')
            col2.metric("投资胜率", f'{stats["win_rate"]*100:.2f}%')
            col3.metric("总投资回报率 (100万本金)", f'{stats["roi"]*100:.2f}%')
            col4.metric("平均持仓周期", f'{stats["avg_hold_days"]:.1f} 天')
            
            # Display DataFrame
            st.subheader("📝 历史交易记录")
            st.dataframe(
                df_trades,
                column_config={
                    "buy_date": "买入日期",
                    "stock_code": "股票代码",
                    "stock_name": "股票名称",
                    "buy_price": st.column_config.NumberColumn("买入价格", format="%.2f"),
                    "sell_date": "卖出日期",
                    "sell_price": st.column_config.NumberColumn("卖出价格", format="%.2f"),
                    "profit_amount": st.column_config.NumberColumn("盈亏金额(以100万计)", format="%.2f"),
                    "profit_percent": st.column_config.NumberColumn("盈利百分比", format="%.2f %%"),
                    "sell_reason": "卖出原因",
                    "hold_days": "持仓周期(天)"
                },
                use_container_width=True,
                hide_index=True,
            )
            
            # Draw a simple chart of cumulative profit if available
            if len(df_trades) > 0:
                df_trades['cumulative_profit'] = df_trades['profit_amount'].cumsum() + 1000000
                st.subheader("💰 资金曲线图")
                st.line_chart(df_trades, x="sell_date", y="cumulative_profit")

if __name__ == "__main__":
    main()

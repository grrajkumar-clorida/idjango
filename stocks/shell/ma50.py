from stocks.backtesting import BacktestEngine
from datetime import datetime, timedelta

# Define stock symbol, exchange, and date range
strategy = "Moving Average Crossover" #"RSI|Moving Average Crossover"
stock_code = "ITC"
exchange = "NSE"
start_date = datetime.now() - timedelta(days=365)
end_date = datetime.now()

# Run the backtest
engine = BacktestEngine(strategy, stock_code, exchange, start_date, end_date)
result = engine.run()

# Print the backtest results
print(result)

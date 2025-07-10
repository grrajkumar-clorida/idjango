from .breeze_client import BreezeAPI
from .models import BacktestResult
from .strategies import moving_average_crossover, rsi_strategy
import pandas as pd

class BacktestEngine:
    def __init__(self, strategy, stock_code, exchange, start_date, end_date, initial_balance=100000):
        self.strategy = strategy
        self.stock_code = stock_code
        self.exchange = exchange
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.breeze = BreezeAPI()
    
    def run(self):
        """ Run backtesting for selected strategy """
        bs = self.breeze.get_session_status()
        
        if bs is True:
            print('Breeze active!')
            df = self.breeze.get_historical_data(self.stock_code, self.exchange, self.start_date, self.end_date)
        else:
            print('eerererer')
                
        if df.empty:
            return None
        
        df["date"] = pd.to_datetime(df["datetime"])
        df.set_index("date", inplace=True)

        # Apply selected strategy
        match self.strategy:
            case "50MA":
                print("You can become a web developer.")
            
            case "RSI":
                print("You can become a Data Scientist")


        if self.strategy == "Moving Average Crossover":
            df = moving_average_crossover(df)
        elif self.strategy == "RSI":
            df = rsi_strategy(df)

        # Simulate Trading Performance
        balance = self.initial_balance
        position = 0
        total_trades = 0
        profits = []
        max_drawdown = 0
        peak_balance = balance

        for i in range(1, len(df)):
            if df["Signal"].iloc[i] == 1:  # Buy
                position = balance / df["close"].iloc[i]
                balance = 0
                total_trades += 1

            elif df["Signal"].iloc[i] == -1 and position > 0:  # Sell
                balance = position * df["close"].iloc[i]
                profits.append(balance - self.initial_balance)
                position = 0
                total_trades += 1

            # Calculate max drawdown
            peak_balance = max(peak_balance, balance)
            drawdown = (peak_balance - balance) / peak_balance if peak_balance != 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        final_balance = balance if balance > 0 else position * df["close"].iloc[-1]
        win_rate = (sum(1 for p in profits if p > 0) / len(profits)) * 100 if profits else 0
        profit_factor = sum(p for p in profits if p > 0) / abs(sum(p for p in profits if p < 0)) if sum(p for p in profits if p < 0) != 0 else float("0")

        # Save backtest results
        BacktestResult.objects.create(
            strategy_name=self.strategy,
            stock_code=self.stock_code,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown
        )
        
        return {
            "Final Balance": final_balance,
            "Total Trades": total_trades,
            "Win Rate (%)": win_rate,
            "Profit Factor": profit_factor,
            "Max Drawdown (%)": max_drawdown
        }

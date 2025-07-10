from django.db import models

class Stock(models.Model):
    stock_code = models.CharField(max_length=10, unique=True)
    script = models.CharField(max_length=50, null=True)
    company_name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, null=True, blank=True)
    
    def __str__(self):
        return self.stock

class StockData(models.Model):
    stock = models.CharField(max_length=10)
    script = models.CharField(max_length=50, null=True)
    exchange = models.CharField(max_length=10)
    interval = models.CharField(max_length=10)
    date = models.DateTimeField()
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.IntegerField()

    def __str__(self):
        return f"{self.stock} ({self.date})"
    
class StockPrice(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    script = models.CharField(max_length=50, null=True)
    date = models.DateField(null=True, default="null")
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.BigIntegerField()

    class Meta:
        unique_together = ('stock', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.stock.stock} - {self.date}"
    

class LiveTrade(models.Model):
    stock_code = models.CharField(max_length=10)
    exchange = models.CharField(max_length=10, default="NSE")
    quantity = models.IntegerField()
    order_type = models.CharField(max_length=10, choices=[("MARKET", "Market"), ("LIMIT", "Limit")])
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    action = models.CharField(max_length=4, choices=[("BUY", "Buy"), ("SELL", "Sell")])
    status = models.CharField(max_length=20, default="Pending")
    order_id = models.CharField(max_length=50, blank=True, null=True)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    trailing_stop_loss = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # NEW
    tsl_percentage = models.FloatField(null=True, blank=True)  # NEW
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # NEW
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.stock_code} - {self.action} - {self.status}"

    # Back testing 
class BacktestResult(models.Model):
    strategy_name = models.CharField(max_length=100)
    stock_code = models.CharField(max_length=10)
    start_date = models.DateField()
    end_date = models.DateField(null=True, default="null")
    initial_balance = models.DecimalField(max_digits=12, decimal_places=2)
    final_balance = models.DecimalField(max_digits=12, decimal_places=2)
    total_trades = models.IntegerField()
    win_rate = models.FloatField()
    profit_factor = models.FloatField()
    max_drawdown = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.strategy_name} - {self.stock_code}"


class MovingAverage(models.Model):
    stock_code = models.CharField(max_length=10)
    sma_20 = models.FloatField()
    sma_50 = models.FloatField()
    open = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    signal = models.FloatField()
    date = models.DateTimeField(null=True, default="null")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)



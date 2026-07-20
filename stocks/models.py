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
    
    # Phase 5.1: Trade Journal Fields
    strategy = models.ForeignKey('Strategy', on_delete=models.SET_NULL, null=True, blank=True, related_name='trades')
    signal = models.ForeignKey('StrategySignal', on_delete=models.SET_NULL, null=True, blank=True, related_name='executed_trades')
    entry_reason = models.TextField(blank=True, help_text="Reason for entering this trade")
    exit_reason = models.TextField(blank=True, help_text="Reason for exiting this trade")
    risk_reward_ratio = models.FloatField(null=True, blank=True, help_text="Risk to reward ratio")
    trade_duration = models.DurationField(null=True, blank=True, help_text="Duration of the trade")
    entry_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    entry_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    market_conditions = models.JSONField(default=dict, blank=True, help_text="Market conditions at trade time")
    notes = models.TextField(blank=True, help_text="Additional trade notes")

    def __str__(self):
        return f"{self.stock_code} - {self.action} - {self.status}"
    
    def calculate_risk_reward(self):
        """Calculate risk-reward ratio"""
        if self.stop_loss and self.take_profit and self.entry_price:
            risk = abs(float(self.entry_price) - float(self.stop_loss))
            reward = abs(float(self.take_profit) - float(self.entry_price))
            if risk > 0:
                self.risk_reward_ratio = reward / risk
                return self.risk_reward_ratio
        return None
    
    def calculate_duration(self):
        """Calculate trade duration"""
        if self.entry_time and self.exit_time:
            self.trade_duration = self.exit_time - self.entry_time
            return self.trade_duration
        return None

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


class Orders(models.Model):
    ticker = models.CharField(max_length=15)
    script = models.CharField(max_length=15)
    order_id = models.CharField(max_length=30)
    position = models.CharField(max_length=26)
    stop_loss = models.FloatField(max_length=6)
    qty = models.CharField(max_length=15)
    price = models.FloatField()
    invested_value = models.FloatField()
    current_value = models.FloatField()
    day_pl = models.FloatField()
    overall_pl = models.FloatField()
    targets = models.JSONField(null=True, blank=True)
    status = models.IntegerField(default=0)
    message = models.CharField(max_length=266)
    user_remark = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class Strategy(models.Model):
    """Registered trading strategies"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    enabled = models.BooleanField(default=False)
    parameters = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Strategies"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({'Enabled' if self.enabled else 'Disabled'})"


class StrategySignal(models.Model):
    """Trading signals generated by strategies"""
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name='signals')
    stock_code = models.CharField(max_length=10, db_index=True)
    signal_type = models.CharField(max_length=10, choices=[("BUY", "Buy"), ("SELL", "Sell"), ("HOLD", "Hold")])
    strength = models.FloatField(default=0.5, help_text="Signal strength 0-1")
    price = models.FloatField(null=True, blank=True)
    stop_loss = models.FloatField(null=True, blank=True)
    take_profit = models.FloatField(null=True, blank=True)
    executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    trade = models.ForeignKey(LiveTrade, on_delete=models.SET_NULL, null=True, blank=True, related_name='signals')
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['stock_code', 'executed']),
            models.Index(fields=['strategy', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.strategy.name} - {self.stock_code} - {self.signal_type} ({'Executed' if self.executed else 'Pending'})"


class RiskLimits(models.Model):
    """Risk management limits"""
    max_position_size = models.DecimalField(max_digits=12, decimal_places=2, default=100000, 
                                           help_text="Maximum position size per trade")
    max_portfolio_exposure = models.DecimalField(max_digits=5, decimal_places=2, default=50.0,
                                                help_text="Maximum portfolio exposure percentage")
    max_daily_loss = models.DecimalField(max_digits=12, decimal_places=2, default=5000,
                                       help_text="Maximum daily loss limit")
    max_drawdown = models.DecimalField(max_digits=5, decimal_places=2, default=10.0,
                                      help_text="Maximum drawdown percentage")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Risk Limits"
    
    def __str__(self):
        return f"Risk Limits (Updated: {self.updated_at})"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and RiskLimits.objects.exists():
            raise ValueError("RiskLimits instance already exists. Use the existing instance.")
        super().save(*args, **kwargs)


class TradeJournal(models.Model):
    """Comprehensive trade journal for analysis and reporting"""
    trade = models.OneToOneField(LiveTrade, on_delete=models.CASCADE, related_name='journal')
    strategy = models.ForeignKey(Strategy, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Trade Details
    stock_code = models.CharField(max_length=10, db_index=True)
    entry_date = models.DateTimeField(db_index=True)
    exit_date = models.DateTimeField(null=True, blank=True)
    entry_price = models.DecimalField(max_digits=10, decimal_places=2)
    exit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantity = models.IntegerField()
    direction = models.CharField(max_length=4, choices=[("BUY", "Buy"), ("SELL", "Sell")])
    
    # Performance Metrics
    pnl = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pnl_percent = models.FloatField(default=0.0)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Risk Metrics
    risk_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    risk_reward_ratio = models.FloatField(null=True, blank=True)
    max_favorable_excursion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_adverse_excursion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Trade Characteristics
    trade_duration = models.DurationField(null=True, blank=True)
    entry_reason = models.TextField(blank=True)
    exit_reason = models.TextField(blank=True)
    market_conditions = models.JSONField(default=dict, blank=True)
    
    # Classification
    trade_type = models.CharField(max_length=20, choices=[
        ("SCALP", "Scalp"),
        ("DAY", "Day Trade"),
        ("SWING", "Swing Trade"),
        ("POSITION", "Position Trade"),
    ], null=True, blank=True)
    win_loss = models.CharField(max_length=10, choices=[
        ("WIN", "Win"),
        ("LOSS", "Loss"),
        ("BREAKEVEN", "Breakeven"),
    ], null=True, blank=True)
    
    # Additional Data
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    screenshots = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-entry_date']
        indexes = [
            models.Index(fields=['strategy', 'entry_date']),
            models.Index(fields=['stock_code', 'entry_date']),
            models.Index(fields=['win_loss', 'entry_date']),
        ]
    
    def __str__(self):
        return f"{self.stock_code} - {self.direction} - {self.entry_date.date()}"
    
    def calculate_pnl_percent(self):
        """Calculate P/L percentage"""
        if self.entry_price and self.exit_price:
            if self.direction == "BUY":
                self.pnl_percent = ((float(self.exit_price) - float(self.entry_price)) / float(self.entry_price)) * 100
            else:  # SELL
                self.pnl_percent = ((float(self.entry_price) - float(self.exit_price)) / float(self.entry_price)) * 100
            return self.pnl_percent
        return 0.0
    
    def calculate_net_pnl(self):
        """Calculate net P/L after commissions"""
        self.net_pnl = float(self.pnl) - float(self.commission)
        return self.net_pnl
    
    def classify_win_loss(self):
        """Classify trade as win, loss, or breakeven"""
        if self.net_pnl > 0:
            self.win_loss = "WIN"
        elif self.net_pnl < 0:
            self.win_loss = "LOSS"
        else:
            self.win_loss = "BREAKEVEN"
        return self.win_loss


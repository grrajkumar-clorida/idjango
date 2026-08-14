from django.db import models

# Create your models here.
class Source(models.Model):
    script = models.CharField(max_length=50, null=True)
    name = models.CharField(max_length=30, null=True)
    trade = models.CharField(max_length=10, null=True)
    market = models.CharField(max_length=10, null=True)
    price = models.FloatField(null=True)
    percent = models.FloatField(null=True)
    notes = models.CharField(max_length=1000, null=True)
    raw_data = models.TextField(null=True)
    status = models.CharField(max_length=20, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.script} - {self.name} - {self.name} ({self.trade})"

class StockPriceData(models.Model):
    stock_code = models.CharField(max_length=10, db_index=True)  # e.g., TCS, INFY
    ticker = models.CharField(max_length=50, null=True)
    date = models.DateField(db_index=True, null=True)  # Trading Date
    close_price = models.FloatField()  # Closing Price
    live50ma = models.FloatField(blank=True, null=True)
    cp50ma = models.FloatField(blank=True, null=True)
    live21ma = models.FloatField(blank=True, null=True)
    live9ma = models.FloatField(blank=True, null=True)
    live921 = models.CharField(max_length=20, db_index=True, null=True)  # 2.64 | 0.63%
    class Meta:
        unique_together = ('stock_code', 'date')  # No duplicates
        ordering = ['-date']

    def __str__(self):
        return f"{self.stock_code} - {self.ticker} - {self.date} - {self.close_price}"

    @classmethod
    def latest_by_stock_code(cls):
        """Latest row per stock_code (ordering is -date). First write wins."""
        mapping = {}
        for row in cls.objects.order_by("-date", "-id"):
            code = (row.stock_code or "").strip()
            if not code:
                continue
            if code not in mapping:
                mapping[code] = row
            upper = code.upper()
            if upper not in mapping:
                mapping[upper] = row
        return mapping

class Stocks50MA(models.Model):
    stock_code = models.CharField(max_length=10, db_index=True)  # Ticker Code (e.g., TCS, INFY)
    ticker = models.CharField(max_length=50, null=True)
    date = models.DateField(db_index=True, blank=True, null=True)  # Date of the MA calculation
    moving_average_50 = models.FloatField()  # 50-Day Moving Average value
    moving_average_20 = models.FloatField(blank=True, null=True)  # 21-Day Moving Average value
    moving_average_09 = models.FloatField(blank=True, null=True)  # 9-Day Moving Average value
    stock_cmp = models.FloatField(blank=True,null=True)
    status = models.IntegerField(default=0)
    cmp_date = models.DateTimeField(blank=True, null=True)
    range_50ma = models.FloatField(blank=True,null=True)
    percent_50ma = models.FloatField(blank=True,null=True)
    range_20ma = models.FloatField(blank=True,null=True)
    percent_20ma = models.FloatField(blank=True,null=True)
    range_09ma = models.FloatField(blank=True,null=True)
    percent_09ma = models.FloatField(blank=True,null=True)
    name = models.CharField(max_length=200, null=True)
    target_1 = models.FloatField(blank=True,null=True)
    target_2 = models.FloatField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now_add=False, null=True)
    # ✅ New field to store snapshot
    pre_data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('stock_code', 'date')  # Ensure no duplicate records
        ordering = ['-date']  # Latest records first
    
    def __str__(self):
        return f" {self.ticker} - CMP:{self.stock_cmp} - 50MA:{self.moving_average_50} - Status {self.status}"

class Stockhalfbat(models.Model):
    stock_code = models.CharField(max_length=10, null=True, db_index=True)
    script = models.CharField(max_length=50, null=True)
    start_date = models.DateField()
    start_swing = models.CharField(max_length=5)
    start_price = models.FloatField()
    end_date = models.DateField()
    end_swing = models.CharField(max_length=5)
    end_price = models.FloatField()
    entry = models.FloatField()
    sl = models.FloatField()
    window = models.IntegerField()
    period = models.CharField(max_length=10)
    direction = models.CharField(max_length=10)
    market = models.CharField(max_length=10)
    moving_average_50 = models.FloatField(null=True, blank=True)
    notes = models.CharField(max_length=1000)
    status = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']  # Latest records first

    def __str__(self):
        return f"{self.script} - {self.direction} ({self.period})"


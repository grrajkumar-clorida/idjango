from django.contrib import admin
from .models import Stock, StockPrice, StockData, BacktestResult

admin.site.register(Stock)
admin.site.register(StockPrice)
admin.site.register(BacktestResult)
@admin.register(StockData)
class StockDataAdmin(admin.ModelAdmin):
    list_display = ("stock", "script", "date", "open_price", "close_price", "volume")

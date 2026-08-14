from django.contrib import admin
from .models import Stock, StockPrice, StockData, BacktestResult, LiveTrade, Orders

admin.site.register(Stock)
admin.site.register(StockPrice)
admin.site.register(BacktestResult)
admin.site.register(StockData)
admin.site.register(LiveTrade)
admin.site.register(Orders)
class StockDataAdmin(admin.ModelAdmin):
    list_display = ("stock", "script", "date", "open_price", "close_price", "volume")

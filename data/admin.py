from django.contrib import admin
from .models import Stocks50MA

# Register your models here.

@admin.register(Stocks50MA)
class Stocks50MAAdmin(admin.ModelAdmin):
    list_display = ('stock_code', 'date', 'moving_average_50')
    list_filter = ('stock_code', 'date')
    search_fields = ('stock_code',)

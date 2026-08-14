from django.contrib import admin
from .models import (
    Stock,
    StockPrice,
    StockData,
    BacktestResult,
    LiveTrade,
    Orders,
    TradeReview,
    Strategy,
    StrategySignal,
    RiskLimits,
)


@admin.register(LiveTrade)
class LiveTradeAdmin(admin.ModelAdmin):
    list_display = (
        "id", "stock_code", "action", "status", "quantity", "remaining_quantity",
        "price", "profit_book_price", "profit_book_qty", "profit_loss", "source",
        "order_id", "timestamp",
    )
    list_filter = ("status", "action", "source", "exchange")
    search_fields = ("stock_code", "order_id")
    list_editable = ("profit_book_price", "profit_book_qty", "status")
    readonly_fields = ("timestamp",)
    fieldsets = (
        (None, {
            "fields": (
                "stock_code", "exchange", "action", "status", "source", "order_id",
            )
        }),
        ("Fill", {
            "fields": (
                "quantity", "remaining_quantity", "order_type", "price",
                "entry_price", "entry_time", "exit_price", "exit_time",
            )
        }),
        ("Human profit booking", {
            "fields": (
                "profit_book_price", "profit_book_qty", "take_profit",
                "stop_loss", "price_min", "price_max",
            )
        }),
        ("P/L", {"fields": ("profit_loss", "notes", "review")}),
    )


@admin.register(TradeReview)
class TradeReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id", "stock_code", "status", "source", "qty", "suggested_price",
        "price_min", "price_max", "take_profit", "take_profit_qty",
        "reviewed_by", "created_at",
    )
    list_filter = ("status", "source", "order_type")
    search_fields = ("stock_code", "ticker", "notes")
    list_editable = (
        "status", "qty", "price_min", "price_max", "take_profit", "take_profit_qty",
    )
    actions = ["approve_selected", "queue_only"]

    def approve_selected(self, request, queryset):
        from data.engine.order_executor import OrderExecutor
        executor = OrderExecutor()
        placed = 0
        for review in queryset:
            review.status = "approved"
            review.reviewed_by = request.user.get_username()[:80]
            review.save()
            result = executor.place_approved_review(review)
            if result.get("success"):
                placed += 1
        self.message_user(request, f"Placed {placed} order(s).")
    approve_selected.short_description = "Approve & place selected"

    def queue_only(self, request, queryset):
        updated = queryset.update(status="approved")
        self.message_user(request, f"{updated} marked approved (beat will place if CMP in range).")
    queue_only.short_description = "Mark approved (do not place now)"


@admin.register(Orders)
class OrdersAdmin(admin.ModelAdmin):
    list_display = (
        "id", "ticker", "order_id", "position", "qty", "price",
        "invested_value", "current_value", "overall_pl", "status", "created_at",
    )
    list_filter = ("status", "position")
    search_fields = ("ticker", "order_id", "script")


admin.site.register(Stock)
admin.site.register(StockPrice)
admin.site.register(BacktestResult)
admin.site.register(StockData)
admin.site.register(Strategy)
admin.site.register(StrategySignal)
admin.site.register(RiskLimits)


class StockDataAdmin(admin.ModelAdmin):
    list_display = ("stock", "script", "date", "open_price", "close_price", "volume")

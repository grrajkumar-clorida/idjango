from django.urls import path, include
from django.contrib.auth.decorators import login_required

from . import views
from . import admin_views
from . import trading_views

auth = login_required

urlpatterns = [
    path("dashboard/", auth(views.stock_dashboard), name="stock_dashboard"),
    path("backtesview/", auth(views.backtest_results_view), name="dashboard"),
    path("backtesresults/", auth(views.backtest_results), name="results"),
    path("itc-price/", auth(views.get_live_price), name="get_live_price"),
    path("web-scr/", auth(views.get_web_data), name="get_web_data"),

    path("review/", auth(trading_views.review_queue), name="desk_review"),
    path("review/suggest/", auth(trading_views.stock_suggest), name="desk_review_suggest"),
    path("review/<int:pk>/approve/", auth(trading_views.review_approve), name="desk_review_approve"),
    path("review/<int:pk>/place/", auth(trading_views.review_place), name="desk_review_place"),
    path("review/<int:pk>/reject/", auth(trading_views.review_reject), name="desk_review_reject"),
    path("review/manual/", auth(trading_views.review_manual), name="desk_review_manual"),
    path("order/", auth(trading_views.order_list), name="desk_orders"),
    path("orders/", auth(trading_views.order_list), name="desk_orders_alias"),
    path("positions/", auth(trading_views.position_list), name="desk_positions"),
    path("positions/", auth(trading_views.position_list), name="stock_positions"),
    path("positions/refresh-prices/", auth(trading_views.position_refresh_prices), name="desk_position_refresh"),
    path("positions/record-fill/", auth(trading_views.position_record_fill), name="desk_position_record_fill"),
    path("positions/import-idirect/", auth(trading_views.position_import_idirect), name="desk_position_import"),
    path("positions/<int:pk>/update/", auth(trading_views.position_update), name="desk_position_update"),

    path("admin/", auth(admin_views.admin_dashboard), name="admin_dashboard"),
    path("admin/dashboard/stats/", auth(admin_views.admin_dashboard_stats), name="admin_dashboard_stats"),
    path("admin/dashboard/recent-signals/", auth(admin_views.admin_recent_signals), name="admin_recent_signals"),
    path("admin/dashboard/system-alerts/", auth(admin_views.admin_system_alerts), name="admin_system_alerts"),

    path("admin/strategies/", auth(admin_views.admin_strategies), name="admin_strategies"),
    path("admin/strategies/table/", auth(admin_views.admin_strategies_table), name="admin_strategies_table"),
    path("admin/strategies/register/", auth(admin_views.admin_strategy_register), name="admin_strategy_register"),
    path("admin/strategies/<int:strategy_id>/", auth(admin_views.admin_strategy_detail), name="admin_strategy_detail"),
    path("admin/strategies/<int:strategy_id>/enable/", auth(admin_views.admin_strategy_enable), name="admin_strategy_enable"),
    path("admin/strategies/<int:strategy_id>/disable/", auth(admin_views.admin_strategy_disable), name="admin_strategy_disable"),

    path("admin/positions/", auth(admin_views.admin_positions), name="admin_positions"),
    path("admin/positions/table/", auth(admin_views.admin_positions_table), name="admin_positions_table"),

    path("admin/performance/", auth(admin_views.admin_performance), name="admin_performance"),

    path("admin/risk/", auth(admin_views.admin_risk), name="admin_risk"),
    path("admin/risk/update/", auth(admin_views.admin_risk_update), name="admin_risk_update"),
    path("admin/risk/alerts/", auth(admin_views.admin_risk_alerts), name="admin_risk_alerts"),

    path("admin/sitemap/", auth(admin_views.admin_sitemap), name="admin_sitemap"),

    path("admin/reports/", auth(admin_views.admin_reports), name="admin_reports"),

    path("api/trading/", include("stocks.api.urls")),
]

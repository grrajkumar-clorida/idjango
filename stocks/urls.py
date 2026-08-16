from django.urls import path, include
from django.contrib.auth.decorators import login_required

from . import views
from . import admin_views
from . import trading_views

urlpatterns = [
    path("dashboard/", views.stock_dashboard, name="stock_dashboard"),
    path('backtesview/', views.backtest_results_view, name='dashboard'),
    path('backtesresults/', views.backtest_results, name='results'),
    path("itc-price/", views.get_live_price, name="get_live_price"),
    path("web-scr/", views.get_web_data, name="get_web_data"),

    # Phase 2 desk (login required)
    path("review/", login_required(trading_views.review_queue), name="desk_review"),
    path("review/suggest/", login_required(trading_views.stock_suggest), name="desk_review_suggest"),
    path("review/<int:pk>/approve/", login_required(trading_views.review_approve), name="desk_review_approve"),
    path("review/<int:pk>/place/", login_required(trading_views.review_place), name="desk_review_place"),
    path("review/<int:pk>/reject/", login_required(trading_views.review_reject), name="desk_review_reject"),
    path("review/manual/", login_required(trading_views.review_manual), name="desk_review_manual"),
    path("order/", login_required(trading_views.order_list), name="desk_orders"),
    path("orders/", login_required(trading_views.order_list), name="desk_orders_alias"),
    path("positions/", login_required(trading_views.position_list), name="desk_positions"),
    path("positions/", login_required(trading_views.position_list), name="stock_positions"),
    path("positions/refresh-prices/", login_required(trading_views.position_refresh_prices), name="desk_position_refresh"),
    path("positions/<int:pk>/update/", login_required(trading_views.position_update), name="desk_position_update"),

    # Admin Dashboard Routes
    path("admin/", admin_views.admin_dashboard, name="admin_dashboard"),
    path("admin/dashboard/stats/", admin_views.admin_dashboard_stats, name="admin_dashboard_stats"),
    path("admin/dashboard/recent-signals/", admin_views.admin_recent_signals, name="admin_recent_signals"),
    path("admin/dashboard/system-alerts/", admin_views.admin_system_alerts, name="admin_system_alerts"),
    
    # Strategies Management
    path("admin/strategies/", admin_views.admin_strategies, name="admin_strategies"),
    path("admin/strategies/table/", admin_views.admin_strategies_table, name="admin_strategies_table"),
    path("admin/strategies/register/", admin_views.admin_strategy_register, name="admin_strategy_register"),
    path("admin/strategies/<int:strategy_id>/", admin_views.admin_strategy_detail, name="admin_strategy_detail"),
    path("admin/strategies/<int:strategy_id>/enable/", admin_views.admin_strategy_enable, name="admin_strategy_enable"),
    path("admin/strategies/<int:strategy_id>/disable/", admin_views.admin_strategy_disable, name="admin_strategy_disable"),
    
    # Positions Management
    path("admin/positions/", admin_views.admin_positions, name="admin_positions"),
    path("admin/positions/table/", admin_views.admin_positions_table, name="admin_positions_table"),
    
    # Performance
    path("admin/performance/", admin_views.admin_performance, name="admin_performance"),
    
    # Risk Management
    path("admin/risk/", admin_views.admin_risk, name="admin_risk"),
    path("admin/risk/update/", admin_views.admin_risk_update, name="admin_risk_update"),
    path("admin/risk/alerts/", admin_views.admin_risk_alerts, name="admin_risk_alerts"),
    
    # Sitemap
    path("admin/sitemap/", admin_views.admin_sitemap, name="admin_sitemap"),
    
    # Reports
    path("admin/reports/", admin_views.admin_reports, name="admin_reports"),
    
    # API endpoints
    path('api/trading/', include('stocks.api.urls')),
]


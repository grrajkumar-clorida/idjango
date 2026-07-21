from django.urls import path, include
from . import views
from . import admin_views
#from .views import stock_dashboard

urlpatterns = [
    path("dashboard/", views.stock_dashboard, name="stock_dashboard"),
    path('backtesview/', views.backtest_results_view, name='dashboard'),
    path('backtesresults/', views.backtest_results, name='results'),
    path("itc-price/", views.get_live_price, name="get_live_price"),
    path("web-scr/", views.get_web_data, name="get_web_data"),
    path("positions/", views.open_positions, name="stock_positions"),
    
    # Admin Dashboard Routes
    path("admin/", admin_views.admin_dashboard, name="admin_dashboard"),
    path("admin/dashboard/stats/", admin_views.admin_dashboard_stats, name="admin_dashboard_stats"),
    path("admin/dashboard/recent-signals/", admin_views.admin_recent_signals, name="admin_recent_signals"),
    path("admin/dashboard/system-alerts/", admin_views.admin_system_alerts, name="admin_system_alerts"),
    
    # Strategies Management
    path("admin/strategies/", admin_views.admin_strategies, name="admin_strategies"),
    path("admin/strategies/table/", admin_views.admin_strategies_table, name="admin_strategies_table"),
    path("admin/strategies/<int:strategy_id>/", admin_views.admin_strategy_detail, name="admin_strategy_detail"),
    path("admin/strategies/<int:strategy_id>/enable/", admin_views.admin_strategy_enable, name="admin_strategy_enable"),
    path("admin/strategies/<int:strategy_id>/disable/", admin_views.admin_strategy_disable, name="admin_strategy_disable"),
    path("admin/strategies/register/", admin_views.admin_strategy_register, name="admin_strategy_register"),
    
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


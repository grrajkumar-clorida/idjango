from django.urls import path
from . import views
#from .views import stock_dashboard

urlpatterns = [
    path("dashboard/", views.stock_dashboard, name="stock_dashboard"),
    path('backtesview/', views.backtest_results_view, name='dashboard'),
    path('backtesresults/', views.backtest_results, name='results'),
    path("itc-price/", views.get_live_price, name="get_live_price"),
    path("web-scr/", views.get_web_data, name="get_web_data"),
    path("positions/", views.open_positions, name="stock_positions")
]


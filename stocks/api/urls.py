"""
API URL Configuration
"""
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Strategy Management
    path('strategies/', views.list_strategies, name='list_strategies'),
    path('strategies/register/', views.register_strategy, name='register_strategy'),
    path('strategies/<int:strategy_id>/status/', views.get_strategy_status, name='strategy_status'),
    path('strategies/<int:strategy_id>/enable/', views.enable_strategy, name='enable_strategy'),
    path('strategies/<int:strategy_id>/disable/', views.disable_strategy, name='disable_strategy'),
    
    # Position Management
    path('positions/', views.list_positions, name='list_positions'),
    path('positions/<int:position_id>/', views.get_position_details, name='position_details'),
    path('positions/<int:position_id>/close/', views.close_position, name='close_position'),
    
    # Performance
    path('performance/', views.get_performance, name='performance'),
    path('performance/<int:strategy_id>/', views.get_strategy_performance, name='strategy_performance'),
    
    # Risk Management
    path('risk/exposure/', views.get_risk_exposure, name='risk_exposure'),
    path('risk/limits/', views.set_risk_limits, name='set_risk_limits'),
    
    # Manual Override
    path('manual/trade/', views.manual_trade, name='manual_trade'),
    path('manual/emergency-stop/', views.emergency_stop, name='emergency_stop'),
    
    # System Status
    path('status/', views.system_status, name='system_status'),
]

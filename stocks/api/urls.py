"""
API URL Configuration — all endpoints require a logged-in user.
"""
from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views

app_name = "api"

auth = login_required

urlpatterns = [
    path("strategies/", auth(views.list_strategies), name="list_strategies"),
    path("strategies/register/", auth(views.register_strategy), name="register_strategy"),
    path("strategies/<int:strategy_id>/status/", auth(views.get_strategy_status), name="strategy_status"),
    path("strategies/<int:strategy_id>/enable/", auth(views.enable_strategy), name="enable_strategy"),
    path("strategies/<int:strategy_id>/disable/", auth(views.disable_strategy), name="disable_strategy"),

    path("positions/", auth(views.list_positions), name="list_positions"),
    path("positions/<int:position_id>/", auth(views.get_position_details), name="position_details"),
    path("positions/<int:position_id>/close/", auth(views.close_position), name="close_position"),

    path("performance/", auth(views.get_performance), name="performance"),
    path("performance/<int:strategy_id>/", auth(views.get_strategy_performance), name="strategy_performance"),

    path("risk/exposure/", auth(views.get_risk_exposure), name="risk_exposure"),
    path("risk/limits/", auth(views.set_risk_limits), name="set_risk_limits"),

    path("manual/trade/", auth(views.manual_trade), name="manual_trade"),
    path("manual/emergency-stop/", auth(views.emergency_stop), name="emergency_stop"),

    path("status/", auth(views.system_status), name="system_status"),
]

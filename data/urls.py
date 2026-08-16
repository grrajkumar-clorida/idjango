from django.urls import path
from django.contrib.auth.decorators import login_required

from . import views

urlpatterns = [
    path("", login_required(views.sma50_dashboard), name="sma50-dashboard"),
    path("source/", login_required(views.chartink_dashboard), name="chartink-source"),
    path("dashboard/", login_required(views.sma50_dashboard), name="sma50-dashboard-page"),
    path("place-order/", login_required(views.place_order), name="place_order"),
]

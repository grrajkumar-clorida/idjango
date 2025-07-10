from django.urls import path
from . import views

urlpatterns = [
    path("", views.sma50_dashboard, name="chartink-dashboard"),
    path("source/", views.chartink_dashboard, name="chartink-dashboard"),
    path("dashboard/", views.sma50_dashboard, name="sma50-dashboard"),
    path("place-order/", views.place_order, name="place_order"),

]

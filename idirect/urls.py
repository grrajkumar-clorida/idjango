from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("infra.urls")),
    path("data/", include("data.urls")),
    path("stocks/", include("stocks.urls")),
]

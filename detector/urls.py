from django.urls import path

from . import views

app_name = "detector"

urlpatterns = [
    path("", views.upload, name="upload"),
    path("history/", views.history, name="history"),
    path("result/<uuid:scan_id>/", views.result, name="result"),
]

from django.urls import path, include
from . import views

urlpatterns = [
    path("setup/", views.setup, name="setup"),
    path("access/", views.get_access_code, name="access"),
    path("list/", views.item_list, name="ticks"),
    path("subscribe/<int:pk>", views.subscribe_instrument, name="subscribe"),
    path("breeze/", views.get_breeze_accounts, name="breeze_account"),
    path("candles/<int:pk>", views.get_instrument_candles, name="get_candles"),
    path(
        "candle_percentage/<int:pk>",
        views.get_instrument_percentage,
        name="get_instrument_percentage",
    ),
    path("delete/<int:pk>", views.delete_instrument, name="delete_instrument"),
    path(
        "subscribed_instruments/",
        views.get_subscribed_instruments,
        name="get_subbed_instruments",
    ),
    path("get_candles/", views.get_candles, name="get_candles"),
    path("get_instruments/", views.get_all_instruments, name="get_instruemnts"),
]

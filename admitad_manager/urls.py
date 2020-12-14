from django.urls import path, re_path, register_converter
from . import views

urlpatterns = [
    path('conversions/', views.google_conversions, name='google_convertions'),
    path('conversion_adjustments/', views.google_conversion_adjustments, name='google_conversion_adjustments'),
]
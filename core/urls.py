from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('generate/', views.generate_qr, name='generate_qr'),
    path('r/<str:short_code>/', views.redirect_qr, name='redirect_qr'),
    path('secure/<str:short_code>/', views.secure_view, name='secure_view'),
    path('analytics/<str:short_code>/', views.analytics_view, name='analytics_view'),
    path('api/generate/', views.api_generate_qr, name='api_generate_qr'),
]

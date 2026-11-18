from django.urls import path

from . import views

urlpatterns = [
    path('temps-reel/', views.LiveDashboardView.as_view(), name='live_dashboard'),
    path('temps-reel/stats/', views.LiveStatsView.as_view(), name='live_stats'),
    path('temps-reel/evenements/', views.LiveEventsView.as_view(), name='live_events'),
]

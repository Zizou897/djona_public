from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.vehicle_list, name='list'),
    path('favoris/', views.vehicle_favorites, name='favorites'),
    path('favoris/toggle/<int:vehicle_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('comparer/', views.vehicle_compare, name='compare'),
    path('comparer/toggle/<int:vehicle_id>/', views.toggle_compare, name='toggle_compare'),
    path('<slug:slug>/', views.vehicle_detail, name='detail'),
]

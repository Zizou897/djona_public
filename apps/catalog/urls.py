from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.vehicle_list, name='list'),
    path('favoris/toggle/<int:vehicle_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('<slug:slug>/', views.vehicle_detail, name='detail'),
]

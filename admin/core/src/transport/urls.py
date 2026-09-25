from django.urls import path

from . import views

urlpatterns = [
    path('transport/', views.TransportRequestListView.as_view(), name='transport_demande_liste'),
    path('transport/types/', views.TransportVehicleTypeListView.as_view(), name='transport_type_liste'),
    path('transport/types/<int:pk>/basculer/', views.TransportVehicleTypeToggleView.as_view(), name='transport_type_basculer'),
    path('transport/<int:pk>/', views.TransportRequestDetailView.as_view(), name='transport_demande_detail'),
]

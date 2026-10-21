from django.urls import path

from . import order_views, views

urlpatterns = [
    path('pieces/', views.PartListView.as_view(), name='part_liste'),
    path('pieces/nouvelle/', views.PartCreateView.as_view(), name='part_creer'),
    path('pieces/import/', views.PartImportView.as_view(), name='part_import'),
    path('pieces/import/modele.csv', views.PartImportSampleView.as_view(), name='part_import_modele'),
    path('pieces/categories/', views.PartCategoryListView.as_view(), name='part_categorie_liste'),
    path('pieces/categories/<int:pk>/', views.PartCategoryUpdateView.as_view(), name='part_categorie_modifier'),
    path('pieces/categories/<int:pk>/basculer/', views.PartCategoryToggleView.as_view(), name='part_categorie_basculer'),
    path('pieces/demandes/', views.PartRequestListView.as_view(), name='part_demande_liste'),
    path('pieces/demandes/<int:pk>/', views.PartRequestDetailView.as_view(), name='part_demande_detail'),
    path('pieces/commandes/', order_views.PartOrderListView.as_view(), name='part_commande_liste'),
    path('pieces/commandes/<int:pk>/', order_views.PartOrderDetailView.as_view(), name='part_commande_detail'),
    path('pieces/livraison/', order_views.DeliveryZoneListView.as_view(), name='part_zone_liste'),
    path('pieces/livraison/<int:pk>/', order_views.DeliveryZoneUpdateView.as_view(), name='part_zone_modifier'),
    path('pieces/livraison/<int:pk>/basculer/', order_views.DeliveryZoneToggleView.as_view(), name='part_zone_basculer'),
    path('pieces/reglages/', order_views.PartsSettingsView.as_view(), name='part_reglages'),
    path('pieces/<int:pk>/', views.PartUpdateView.as_view(), name='part_modifier'),
    path('pieces/<int:pk>/basculer/', views.PartToggleView.as_view(), name='part_basculer'),
    path('pieces/<int:pk>/supprimer/', views.PartDeleteView.as_view(), name='part_supprimer'),
]

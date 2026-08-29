from django.urls import path

from . import views

urlpatterns = [
    path('vendeurs/', views.VendeurListView.as_view(), name='vendeur_liste'),
    path('vendeurs/<int:pk>/activer/', views.VendeurActiverView.as_view(), name='vendeur_activer'),
    path('vendeurs/<int:pk>/suspendre/', views.VendeurSuspendreView.as_view(), name='vendeur_suspendre'),
    path('annonces-a-valider/', views.AnnonceModerationListView.as_view(), name='annonce_moderation_liste'),
    path('annonces-a-valider/<int:pk>/', views.AnnonceModerationDetailView.as_view(), name='annonce_moderation_detail'),
    path('annonces-a-valider/<int:pk>/valider/', views.AnnonceValiderView.as_view(), name='annonce_valider'),
    path('annonces-a-valider/<int:pk>/refuser/', views.AnnonceRefuserView.as_view(), name='annonce_refuser'),
]

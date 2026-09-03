from django.urls import path

from . import views

urlpatterns = [
    path('', views.MesAnnoncesListView.as_view(), name='mes_annonces'),
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
    path('<int:pk>/modifier/', views.AnnonceUpdateView.as_view(), name='annonce_modifier'),
    path('<int:pk>/publier/', views.AnnoncePublierView.as_view(), name='annonce_publier'),
    path('<int:pk>/supprimer/', views.AnnonceDeleteView.as_view(), name='annonce_supprimer'),
]

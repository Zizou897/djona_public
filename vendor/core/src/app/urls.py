from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('inscription/', views.InscriptionView.as_view(), name='inscription_vendeur'),
    path('connexion/', views.ConnexionView.as_view(), name='connexion_vendeur'),
    path('deconnexion/', LogoutView.as_view(), name='deconnexion_vendeur'),
    path('tableau-de-bord/', views.TableauDeBordVendeurView.as_view(), name='tableau_de_bord_vendeur'),
    path('profil/', views.ProfilVendeurView.as_view(), name='profil_vendeur'),
    path('profil/mot-de-passe/', views.ProfilPasswordChangeView.as_view(), name='profil_vendeur_mot_de_passe'),
]

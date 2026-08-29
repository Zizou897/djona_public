from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('connexion/', views.AdminLoginView.as_view(), name='connexion_admin'),
    path('deconnexion/', LogoutView.as_view(), name='deconnexion_admin'),
    path('tableau-de-bord/', views.AdminDashboardView.as_view(), name='dashboard_admin'),
    path('profil/', views.ProfilView.as_view(), name='profil_admin'),
    path('profil/mot-de-passe/', views.ProfilPasswordChangeView.as_view(), name='profil_mot_de_passe'),
]

from django.urls import path

from . import views

urlpatterns = [
    path('', views.EspaceProDashboardView.as_view(), name='espace_pro_dashboard'),
    path('equipe/', views.EquipeListView.as_view(), name='espace_pro_equipe'),
    path('equipe/inviter/', views.EquipeInviterView.as_view(), name='espace_pro_equipe_inviter'),
    path('equipe/<int:pk>/suspendre/', views.EquipeToggleActifView.as_view(), name='espace_pro_equipe_toggle'),
    path('equipe/<int:pk>/retirer/', views.EquipeRetirerView.as_view(), name='espace_pro_equipe_retirer'),
    path('prospects/', views.ProspectListView.as_view(), name='espace_pro_prospects'),
    path('prospects/ajouter/', views.ProspectCreateView.as_view(), name='espace_pro_prospect_creer'),
    path('prospects/<int:pk>/statut/', views.ProspectUpdateStatutView.as_view(), name='espace_pro_prospect_statut'),
    path('prospects/<int:pk>/supprimer/', views.ProspectDeleteView.as_view(), name='espace_pro_prospect_supprimer'),
]

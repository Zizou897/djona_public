from django.urls import path

from . import views

urlpatterns = [
    path('partenaires/', views.PartnerListView.as_view(), name='partner_liste'),
    path('partenaires/ajouter/', views.PartnerCreateView.as_view(), name='partner_creer'),
    path('partenaires/<int:pk>/modifier/', views.PartnerUpdateView.as_view(), name='partner_modifier'),
    path('partenaires/<int:pk>/supprimer/', views.PartnerDeleteView.as_view(), name='partner_supprimer'),
]

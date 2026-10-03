from django.urls import path

from . import views

urlpatterns = [
    path('messages/', views.ContactMessageListView.as_view(), name='contact_message_liste'),
    path('messages/coordonnees/', views.SiteContactUpdateView.as_view(), name='site_contact_coordonnees'),
    path('messages/<int:pk>/', views.ContactMessageDetailView.as_view(), name='contact_message_detail'),
]

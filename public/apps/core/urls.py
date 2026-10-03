from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('a-propos/', views.about, name='about'),
    path('avantages-djona/', views.avantages, name='avantages'),
    path('contact/', views.contact, name='contact'),
    path('contact/merci/', views.contact_success, name='contact_success'),
    path('questions/', views.ask_question, name='ask_question'),
    path('confidentialite/', views.privacy, name='privacy'),
    path('cgu/', views.terms, name='terms'),
    path('conditions-vendeurs/', views.seller_terms, name='seller_terms'),
    path('transport-logistique/', views.transport, name='transport'),
    path('transport-logistique/merci/', views.transport_success, name='transport_success'),
    path('pieces-detachees/', views.pieces, name='pieces'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('newsletter/', views.newsletter_subscribe, name='newsletter_subscribe'),
]

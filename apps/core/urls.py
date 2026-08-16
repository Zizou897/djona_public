from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('confidentialite/', views.privacy, name='privacy'),
    path('cgu/', views.terms, name='terms'),
    path('conditions-vendeurs/', views.seller_terms, name='seller_terms'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
]

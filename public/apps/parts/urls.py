from django.urls import path

from . import views

app_name = 'parts'

urlpatterns = [
    path('', views.home, name='home'),
    path('catalogue/', views.search, name='search'),
    path('modeles/', views.models_options, name='models'),
    path('introuvable/', views.request_part, name='request'),
    path('introuvable/merci/', views.request_success, name='request_success'),
    path('interesse/<int:pk>/', views.interest, name='interest'),
    path('<int:pk>-<slug:slug>/', views.detail, name='detail'),
]

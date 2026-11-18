from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('collect/', views.collect, name='collect'),
]

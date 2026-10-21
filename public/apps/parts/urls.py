from django.urls import path

from . import order_views, views

app_name = 'parts'

urlpatterns = [
    path('', views.home, name='home'),
    path('catalogue/', views.search, name='search'),
    path('modeles/', views.models_options, name='models'),
    path('introuvable/', views.request_part, name='request'),
    path('introuvable/merci/', views.request_success, name='request_success'),
    path('interesse/<int:pk>/', views.interest, name='interest'),
    path('panier/', order_views.cart_view, name='cart'),
    path('panier/ajouter/<int:pk>/', order_views.cart_add, name='cart_add'),
    path('panier/modifier/<int:pk>/', order_views.cart_update, name='cart_update'),
    path('panier/retirer/<int:pk>/', order_views.cart_remove, name='cart_remove'),
    path('commander/', order_views.checkout, name='checkout'),
    path('commande/merci/', order_views.order_success, name='order_success'),
    path('suivi/', order_views.track, name='track'),
    path('<int:pk>-<slug:slug>/', views.detail, name='detail'),
]

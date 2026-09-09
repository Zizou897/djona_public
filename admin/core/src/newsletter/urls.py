from django.urls import path

from . import views

urlpatterns = [
    path('newsletter/', views.NewsletterSubscriberListView.as_view(), name='newsletter_subscriber_liste'),
    path('newsletter/export/', views.NewsletterSubscriberExportView.as_view(), name='newsletter_subscriber_export'),
    path('newsletter/<int:pk>/supprimer/', views.NewsletterSubscriberDeleteView.as_view(), name='newsletter_subscriber_supprimer'),
]

import csv

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from app.views import StaffRequisMixin

from .models import NewsletterSubscriberMirror


class NewsletterSubscriberListView(StaffRequisMixin, ListView):
    template_name = 'newsletter/subscriber_liste.html'
    context_object_name = 'subscribers'

    def get_queryset(self):
        return NewsletterSubscriberMirror.objects.using('public_db').filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nb_total'] = len(context['subscribers'])
        return context


class NewsletterSubscriberDeleteView(StaffRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        subscriber = get_object_or_404(NewsletterSubscriberMirror.objects.using('public_db'), pk=pk)
        subscriber.delete(using='public_db')
        messages.success(request, 'Abonné retiré de la newsletter.')
        return redirect('newsletter_subscriber_liste')


class NewsletterSubscriberExportView(StaffRequisMixin, View):
    def get(self, request):
        subscribers = NewsletterSubscriberMirror.objects.using('public_db').filter(is_active=True)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="newsletter-djona.csv"'
        writer = csv.writer(response)
        writer.writerow(['email', 'inscrit le'])
        for subscriber in subscribers:
            writer.writerow([subscriber.email, subscriber.created_at.strftime('%Y-%m-%d %H:%M')])
        return response

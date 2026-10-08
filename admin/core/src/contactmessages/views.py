from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from app.views import StaffRequisMixin

from .forms import SiteContactForm
from .models import ContactMessageMirror, SiteContactMirror


class ContactMessageListView(StaffRequisMixin, ListView):
    template_name = 'contactmessages/message_liste.html'
    context_object_name = 'messages_contact'

    def get_queryset(self):
        qs = ContactMessageMirror.objects.using('public_db').all()
        statut = self.request.GET.get('statut')
        if statut in ContactMessageMirror.Status.values:
            qs = qs.filter(status=statut)
        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            qs = qs.filter(
                Q(full_name__icontains=recherche) | Q(phone__icontains=recherche)
                | Q(email__icontains=recherche) | Q(message__icontains=recherche)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = ContactMessageMirror.objects.using('public_db').values('status').annotate(n=Count('id'))
        counts = {row['status']: row['n'] for row in rows}
        context['statuts'] = [
            {'value': value, 'label': label, 'count': counts.get(value, 0)}
            for value, label in ContactMessageMirror.Status.choices
        ]
        context['statut_actif'] = self.request.GET.get('statut', '')
        context['recherche'] = self.request.GET.get('q', '')
        context['nb_total'] = sum(counts.values())
        return context


class ContactMessageDetailView(StaffRequisMixin, View):
    template_name = 'contactmessages/message_detail.html'

    def get_message(self, pk):
        return get_object_or_404(ContactMessageMirror.objects.using('public_db'), pk=pk)

    def get(self, request, pk):
        return render(request, self.template_name, {
            'msg': self.get_message(pk),
            'statuts': ContactMessageMirror.Status.choices,
        })

    def post(self, request, pk):
        msg = self.get_message(pk)
        statut = request.POST.get('statut')
        if statut not in ContactMessageMirror.Status.values:
            messages.error(request, 'Statut invalide.')
        else:
            msg.status = statut
            msg.save(using='public_db', update_fields=['status', 'updated_at'])
            messages.success(request, 'Message : statut mis à jour.')
        return redirect('contact_message_detail', pk=pk)


class SiteContactUpdateView(StaffRequisMixin, View):
    template_name = 'contactmessages/coordonnees.html'

    def get_instance(self):
        return get_object_or_404(SiteContactMirror.objects.using('public_db'), pk=1)

    def get(self, request):
        return render(request, self.template_name, {'form': SiteContactForm(instance=self.get_instance())})

    def post(self, request):
        form = SiteContactForm(request.POST, instance=self.get_instance())
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        form.save(commit=False).save(using='public_db')
        messages.success(request, 'Coordonnées mises à jour : elles sont déjà visibles sur le site.')
        return redirect('site_contact_coordonnees')

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from app.views import StaffRequisMixin

from .forms import TransportVehicleTypeForm
from .models import TransportRequestMirror, TransportVehicleTypeMirror


class TransportRequestListView(StaffRequisMixin, ListView):
    template_name = 'transport/demande_liste.html'
    context_object_name = 'demandes'

    def get_queryset(self):
        qs = TransportRequestMirror.objects.using('public_db').select_related('vehicle_type')
        statut = self.request.GET.get('statut')
        if statut in TransportRequestMirror.Status.values:
            qs = qs.filter(status=statut)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = TransportRequestMirror.objects.using('public_db').values('status').annotate(n=Count('id'))
        counts = {row['status']: row['n'] for row in rows}
        context['statuts'] = [
            {'value': value, 'label': label, 'count': counts.get(value, 0)}
            for value, label in TransportRequestMirror.Status.choices
        ]
        context['statut_actif'] = self.request.GET.get('statut', '')
        context['nb_total'] = sum(counts.values())
        return context


class TransportRequestDetailView(StaffRequisMixin, View):
    template_name = 'transport/demande_detail.html'

    def get_demande(self, pk):
        return get_object_or_404(
            TransportRequestMirror.objects.using('public_db').select_related('vehicle_type'), pk=pk,
        )

    def get(self, request, pk):
        return render(request, self.template_name, {
            'demande': self.get_demande(pk),
            'statuts': TransportRequestMirror.Status.choices,
        })

    def post(self, request, pk):
        demande = self.get_demande(pk)
        statut = request.POST.get('statut')
        if statut not in TransportRequestMirror.Status.values:
            messages.error(request, 'Statut invalide.')
        else:
            demande.status = statut
            demande.save(using='public_db', update_fields=['status', 'updated_at'])
            messages.success(request, f'Demande {demande.reference} : statut mis à jour.')
        return redirect('transport_demande_detail', pk=pk)


class TransportVehicleTypeListView(StaffRequisMixin, View):
    template_name = 'transport/type_liste.html'

    def render_page(self, request, form):
        return render(request, self.template_name, {
            'types': TransportVehicleTypeMirror.objects.using('public_db').all(),
            'form': form,
        })

    def get(self, request):
        return self.render_page(request, TransportVehicleTypeForm())

    def post(self, request):
        form = TransportVehicleTypeForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, form)
        form.save(commit=False).save(using='public_db')
        messages.success(request, 'Type de véhicule ajouté.')
        return redirect('transport_type_liste')


class TransportVehicleTypeToggleView(StaffRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        type_ = get_object_or_404(TransportVehicleTypeMirror.objects.using('public_db'), pk=pk)
        type_.is_active = not type_.is_active
        type_.save(using='public_db', update_fields=['is_active'])
        etat = 'actif' if type_.is_active else 'masqué'
        messages.success(request, f'« {type_.name} » est désormais {etat} dans le formulaire.')
        return redirect('transport_type_liste')

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from app.views import StaffRequisMixin

from .forms import PartnerForm
from .models import PartnerMirror


class PartnerListView(StaffRequisMixin, ListView):
    template_name = 'partners/partner_liste.html'
    context_object_name = 'partners'

    def get_queryset(self):
        return PartnerMirror.objects.using('public_db').all()


class PartnerCreateView(StaffRequisMixin, View):
    template_name = 'partners/partner_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': PartnerForm()})

    def post(self, request):
        form = PartnerForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        partner = form.save(commit=False)
        partner.save(using='public_db')
        messages.success(request, 'Partenaire ajouté.')
        return redirect('partner_liste')


class PartnerUpdateView(StaffRequisMixin, View):
    template_name = 'partners/partner_form.html'

    def get_partner(self, pk):
        return get_object_or_404(PartnerMirror.objects.using('public_db'), pk=pk)

    def get(self, request, pk):
        partner = self.get_partner(pk)
        return render(request, self.template_name, {'form': PartnerForm(instance=partner), 'partner': partner})

    def post(self, request, pk):
        partner = self.get_partner(pk)
        form = PartnerForm(request.POST, request.FILES, instance=partner)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'partner': partner})

        partner = form.save(commit=False)
        partner.save(using='public_db')
        messages.success(request, 'Partenaire mis à jour.')
        return redirect('partner_liste')


class PartnerDeleteView(StaffRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        partner = get_object_or_404(PartnerMirror.objects.using('public_db'), pk=pk)
        partner.delete(using='public_db')
        messages.success(request, 'Partenaire supprimé.')
        return redirect('partner_liste')

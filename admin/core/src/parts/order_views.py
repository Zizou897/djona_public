from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from app.views import StaffRequisMixin

from .forms import INPUT_CLASS, style
from .models import (DeliveryZoneMirror, PartOrderEventMirror, PartOrderMirror, PartsSettingsMirror)

DB = 'public_db'


# ── Formulaires ──────────────────────────────────────────────────────────────

class OrderFollowUpForm(forms.ModelForm):
    """Frais, paiement, commission et note interne d'une commande."""

    class Meta:
        model = PartOrderMirror
        fields = ['delivery_fee', 'commission_amount', 'payment_status', 'payment_method', 'payment_reference',
                  'amount_paid', 'internal_note']
        widgets = {'internal_note': forms.Textarea(attrs={'rows': 3})}
        help_texts = {
            'delivery_fee': "Frais confirmés au client (vide = à confirmer). Zéro pour un retrait.",
            'commission_amount': 'Calculée à la commande selon la règle des réglages ; modifiable ici.',
            'internal_note': 'Visible uniquement par le staff.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def clean(self):
        cleaned = super().clean()
        order = self.instance
        paid = cleaned.get('amount_paid') or 0
        total = order.subtotal + (cleaned.get('delivery_fee') or 0)
        if paid > total and order.total_is_final:
            self.add_error('amount_paid', f'Le montant payé dépasse le total de la commande ({total} FCFA).')
        return cleaned


class DeliveryZoneForm(forms.ModelForm):
    class Meta:
        model = DeliveryZoneMirror
        fields = ['name', 'fee', 'lead_time', 'order']
        labels = {'name': 'Zone', 'fee': 'Frais (FCFA)', 'lead_time': 'Délai estimé', 'order': 'Ordre'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def validate_unique(self):
        pass

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = DeliveryZoneMirror.objects.using(DB).filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Cette zone existe déjà.')
        return name


class PartsSettingsForm(forms.ModelForm):
    class Meta:
        model = PartsSettingsMirror
        fields = ['commission_type', 'commission_value', 'payment_terms', 'pickup_instructions']
        widgets = {'payment_terms': forms.Textarea(attrs={'rows': 3}), 'pickup_instructions': forms.Textarea(attrs={'rows': 3})}
        help_texts = {
            'commission_type': 'Aucun taux n\'est défini par défaut : sans règle, aucune commission n\'est calculée.',
            'commission_value': 'Pourcentage (ex : 8) ou montant en FCFA selon la règle choisie.',
            'payment_terms': 'Affiché au client à la commande. Laissez vide tant que les modalités ne sont pas arrêtées.',
            'pickup_instructions': 'Affiché au client qui choisit le retrait. Vide = « confirmé par l\'équipe ».',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def clean(self):
        cleaned = super().clean()
        kind, value = cleaned.get('commission_type'), cleaned.get('commission_value')
        if kind in ('pourcentage', 'fixe') and not value:
            self.add_error('commission_value', 'Indiquez la valeur de la règle de commission.')
        if kind == 'pourcentage' and value and value > 100:
            self.add_error('commission_value', 'Un pourcentage ne peut pas dépasser 100.')
        if kind == 'aucune':
            cleaned['commission_value'] = None
        return cleaned


# ── Commandes ────────────────────────────────────────────────────────────────

class PartOrderListView(StaffRequisMixin, View):
    template_name = 'parts/commande_liste.html'

    def get(self, request):
        qs = PartOrderMirror.objects.using(DB).annotate(nb_lignes=Count('lines'))
        statut = request.GET.get('statut', '')
        if statut in PartOrderMirror.Status.values:
            qs = qs.filter(status=statut)
        reception = request.GET.get('reception', '')
        if reception in ('retrait', 'livraison'):
            qs = qs.filter(reception=reception)
        paiement = request.GET.get('paiement', '')
        if paiement in PartOrderMirror.PaymentStatus.values:
            qs = qs.filter(payment_status=paiement)
        recherche = request.GET.get('q', '').strip()
        if recherche:
            qs = qs.filter(Q(reference__icontains=recherche) | Q(full_name__icontains=recherche)
                           | Q(company_name__icontains=recherche) | Q(phone__icontains=recherche)
                           | Q(lines__reference__icontains=recherche) | Q(lines__name__icontains=recherche)).distinct()
        rows = PartOrderMirror.objects.using(DB).values('status').annotate(n=Count('id'))
        counts = {row['status']: row['n'] for row in rows}
        return render(request, self.template_name, {
            'commandes': qs,
            'statuts': [{'value': v, 'label': l, 'count': counts.get(v, 0)} for v, l in PartOrderMirror.Status.choices],
            'statut_actif': statut, 'reception_active': reception, 'paiement_actif': paiement, 'recherche': recherche,
            'paiements': PartOrderMirror.PaymentStatus.choices,
            'nb_total': sum(counts.values()),
        })


class PartOrderDetailView(StaffRequisMixin, View):
    template_name = 'parts/commande_detail.html'

    def get_order(self, pk):
        return get_object_or_404(PartOrderMirror.objects.using(DB).prefetch_related('lines', 'events'), pk=pk)

    def render_page(self, request, order, form=None):
        return render(request, self.template_name, {
            'commande': order,
            'form': form or OrderFollowUpForm(instance=order),
            'suivants': [(s.value, s.label) for s in order.next_statuses()],
            'statuts': PartOrderMirror.Status,
        })

    def get(self, request, pk):
        return self.render_page(request, self.get_order(pk))

    def post(self, request, pk):
        order = self.get_order(pk)
        action = request.POST.get('action')
        if action == 'statut':
            return self.change_status(request, order)
        form = OrderFollowUpForm(request.POST, instance=order)
        if not form.is_valid():
            return self.render_page(request, order, form)
        with transaction.atomic(using=DB):
            changed = ', '.join(form.changed_data)
            form.save(commit=False).save(using=DB)
            if changed:
                PartOrderEventMirror.objects.using(DB).create(order=order, note='Mise à jour : ' + ', '.join(
                    str(form.fields[name].label or name).lower() for name in form.changed_data)[:240])
        messages.success(request, f'Commande {order.reference} mise à jour.')
        return redirect('part_commande_detail', pk=pk)

    def change_status(self, request, order):
        new = request.POST.get('statut', '')
        note = request.POST.get('note', '').strip()[:240]
        allowed = {s.value for s in order.next_statuses()}
        if new not in allowed:
            messages.error(request, 'Changement de statut impossible depuis « %s ».' % order.get_status_display())
            return redirect('part_commande_detail', pk=order.pk)
        with transaction.atomic(using=DB):
            order.status = new
            order.save(using=DB, update_fields=['status', 'updated_at'])
            PartOrderEventMirror.objects.using(DB).create(order=order, status=new, note=note)
        messages.success(request, f'Commande {order.reference} : {order.get_status_display().lower()}.')
        return redirect('part_commande_detail', pk=order.pk)


# ── Zones de livraison ───────────────────────────────────────────────────────

class DeliveryZoneListView(StaffRequisMixin, View):
    template_name = 'parts/zone_liste.html'

    def render_page(self, request, form):
        return render(request, self.template_name, {'zones': DeliveryZoneMirror.objects.using(DB).all(), 'form': form})

    def get(self, request):
        return self.render_page(request, DeliveryZoneForm())

    def post(self, request):
        form = DeliveryZoneForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, form)
        form.save(commit=False).save(using=DB)
        messages.success(request, 'Zone de livraison ajoutée.')
        return redirect('part_zone_liste')


class _PostOnly(StaffRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class DeliveryZoneUpdateView(_PostOnly):
    def post(self, request, pk):
        zone = get_object_or_404(DeliveryZoneMirror.objects.using(DB), pk=pk)
        form = DeliveryZoneForm(request.POST, instance=zone)
        if form.is_valid():
            form.save(commit=False).save(using=DB)
            messages.success(request, f'Zone « {zone.name} » mise à jour.')
        else:
            messages.error(request, 'Zone non modifiée : ' + ' '.join(e for errs in form.errors.values() for e in errs))
        return redirect('part_zone_liste')


class DeliveryZoneToggleView(_PostOnly):
    def post(self, request, pk):
        zone = get_object_or_404(DeliveryZoneMirror.objects.using(DB), pk=pk)
        zone.is_active = not zone.is_active
        zone.save(using=DB, update_fields=['is_active'])
        messages.success(request, f'« {zone.name} » est désormais {"proposée" if zone.is_active else "masquée"} aux clients.')
        return redirect('part_zone_liste')


# ── Réglages ─────────────────────────────────────────────────────────────────

class PartsSettingsView(StaffRequisMixin, View):
    template_name = 'parts/reglages.html'

    def get_instance(self):
        instance, _ = PartsSettingsMirror.objects.using(DB).get_or_create(pk=1)
        return instance

    def get(self, request):
        return render(request, self.template_name, {'form': PartsSettingsForm(instance=self.get_instance())})

    def post(self, request):
        form = PartsSettingsForm(request.POST, instance=self.get_instance())
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        form.save(commit=False).save(using=DB)
        messages.success(request, 'Réglages enregistrés.')
        return redirect('part_reglages')

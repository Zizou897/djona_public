from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import AnnonceMirror, CompteVendeur
from .sync import trigger_public_sync


class VendeurListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CompteVendeur
    template_name = 'moderation/vendeur_liste.html'
    context_object_name = 'vendeurs'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    def get_queryset(self):
        # en_attente affiché en premier (ordre alphabétique du statut : actif < en_attente < suspendu
        # ne convient pas — tri explicite par priorité de traitement).
        statut_order = {
            CompteVendeur.StatutCompte.EN_ATTENTE: 0,
            CompteVendeur.StatutCompte.ACTIF: 1,
            CompteVendeur.StatutCompte.SUSPENDU: 2,
        }
        vendeurs = list(CompteVendeur.objects.using('vendor_db').all())
        vendeurs.sort(key=lambda v: (statut_order.get(v.statut_compte, 99), v.nom))
        return vendeurs


class _VendeurActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    login_url = 'connexion_admin'
    nouveau_statut = None

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        vendeur = get_object_or_404(CompteVendeur.objects.using('vendor_db'), pk=pk)
        vendeur.statut_compte = self.nouveau_statut
        vendeur.save(using='vendor_db', update_fields=['statut_compte'])
        return redirect('vendeur_liste')


class VendeurActiverView(_VendeurActionView):
    nouveau_statut = CompteVendeur.StatutCompte.ACTIF


class VendeurSuspendreView(_VendeurActionView):
    nouveau_statut = CompteVendeur.StatutCompte.SUSPENDU


class AnnonceModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'moderation/annonce_liste.html'
    context_object_name = 'annonces'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    def get_queryset(self):
        return (
            AnnonceMirror.objects.using('vendor_db')
            .filter(statut=AnnonceMirror.Statut.EN_ATTENTE)
            .select_related('vendeur')
            .order_by('created_at')
        )


class AnnonceModerationDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'moderation/annonce_detail.html'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    def get(self, request, pk):
        annonce = get_object_or_404(
            AnnonceMirror.objects.using('vendor_db').select_related('vendeur'), pk=pk,
        )
        photos = annonce.photos.using('vendor_db').all()
        return render(request, self.template_name, {'annonce': annonce, 'photos': photos})


class _AnnonceActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    login_url = 'connexion_admin'
    nouveau_statut = None

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        annonce = get_object_or_404(AnnonceMirror.objects.using('vendor_db'), pk=pk)
        if annonce.statut == AnnonceMirror.Statut.EN_ATTENTE:
            annonce.statut = self.nouveau_statut
            annonce.save(using='vendor_db', update_fields=['statut'])
            if self.nouveau_statut == AnnonceMirror.Statut.PUBLIEE:
                trigger_public_sync.after_response()
        return redirect('annonce_moderation_liste')


class AnnonceValiderView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.PUBLIEE


class AnnonceRefuserView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.REFUSEE

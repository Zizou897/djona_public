from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, redirect_to_login
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from .forms import ProfilForm, UtilisateurInfoForm
from .models import Profil
from moderation.models import AnnonceMirror, CompteVendeur


def home(request):
    return render(request, 'app/layout/index.html', {})


class AdminLoginView(LoginView):
    template_name = 'app/layout/connexion_admin.html'

    @property
    def redirect_authenticated_user(self):
        # Ne rediriger automatiquement que les utilisateurs déjà connectés ET
        # autorisés (staff). Sans cette condition, un utilisateur non-staff
        # renvoyé ici avec un `next=` par une vue protégée (AdminDashboardView,
        # AnnonceCreateView, ...) serait aussitôt redirigé vers cette même
        # page protégée, provoquant une boucle de redirection infinie au lieu
        # d'afficher le formulaire de connexion.
        return self.request.user.is_authenticated and self.request.user.is_staff


class StaffRequisMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Garde commune aux vues du backoffice admin : connecté + is_staff."""

    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )


class AdminDashboardView(StaffRequisMixin, TemplateView):
    template_name = 'app/layout/dashboard_admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        annonces_publiees = AnnonceMirror.objects.using('vendor_db').filter(
            statut=AnnonceMirror.Statut.PUBLIEE,
        ).count()
        annonces_en_attente_total = AnnonceMirror.objects.using('vendor_db').filter(
            statut=AnnonceMirror.Statut.EN_ATTENTE,
        ).count()

        vendeurs_particuliers = CompteVendeur.objects.using('vendor_db').filter(
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
        ).count()
        vendeurs_professionnels = CompteVendeur.objects.using('vendor_db').filter(
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL,
        ).count()

        annonces_en_attente = list(
            AnnonceMirror.objects.using('vendor_db')
            .filter(statut=AnnonceMirror.Statut.EN_ATTENTE)
            .select_related('vendeur')
            .order_by('-created_at')[:5]
        )

        activites = []
        for vendeur in CompteVendeur.objects.using('vendor_db').order_by('-date_joined')[:6]:
            activites.append({
                'type': 'inscription',
                'titre': 'Nouvelle inscription vendeur',
                'description': (
                    f'{vendeur.prenom} {vendeur.nom} a créé un compte '
                    f'{vendeur.get_type_compte_display().lower()}.'
                ),
                'date': vendeur.date_joined,
            })
        for annonce in (
            AnnonceMirror.objects.using('vendor_db')
            .select_related('vendeur')
            .order_by('-created_at')[:6]
        ):
            activites.append({
                'type': 'annonce',
                'titre': 'Nouvelle annonce',
                'description': (
                    f'Annonce {annonce.marque} {annonce.modele} soumise par '
                    f'{annonce.vendeur.prenom} {annonce.vendeur.nom}.'
                ),
                'date': annonce.created_at,
            })
        activites.sort(key=lambda evenement: evenement['date'], reverse=True)

        context.update({
            'annonces_publiees': annonces_publiees,
            'annonces_en_attente_total': annonces_en_attente_total,
            'annonces_total': annonces_publiees + annonces_en_attente_total,
            'vendeurs_particuliers': vendeurs_particuliers,
            'vendeurs_professionnels': vendeurs_professionnels,
            'vendeurs_total': vendeurs_particuliers + vendeurs_professionnels,
            'annonces_en_attente': annonces_en_attente,
            'activites_recentes': activites[:6],
        })
        return context


class ProfilView(StaffRequisMixin, View):
    template_name = 'app/layout/profil_admin.html'

    def _context(self, request, info_form=None, profil_form=None):
        profil, _ = Profil.objects.get_or_create(user=request.user)
        if info_form is None:
            info_form = UtilisateurInfoForm(initial={
                'nom_complet': f'{request.user.first_name} {request.user.last_name}'.strip(),
                'email': request.user.email,
            })
        if profil_form is None:
            profil_form = ProfilForm(instance=profil)
        return {
            'profil': profil,
            'info_form': info_form,
            'profil_form': profil_form,
            'securite_pourcentage': 100 if profil.two_factor_enabled else 50,
        }

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        profil, _ = Profil.objects.get_or_create(user=request.user)
        info_form = UtilisateurInfoForm(request.POST)
        profil_form = ProfilForm(request.POST, request.FILES, instance=profil)

        if info_form.is_valid() and profil_form.is_valid():
            with transaction.atomic():
                info_form.save(request.user)
                profil_form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('profil_admin')

        messages.error(request, 'Merci de corriger les erreurs ci-dessous.')
        return render(request, self.template_name, self._context(request, info_form, profil_form))


class ProfilPasswordChangeView(StaffRequisMixin, View):
    def post(self, request):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Mot de passe modifié avec succès.')
        else:
            for error_list in form.errors.values():
                messages.error(request, error_list.as_text())
        return redirect('profil_admin')

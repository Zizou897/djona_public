import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView,
)
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView

from annonces.forms import MIN_PHOTOS
from annonces.models import Annonce
from . import throttle
from .forms import (
    ConnexionForm, DemandePassageProForm, InscriptionForm, MotDePasseOublieForm, NouveauMotDePasseForm, ProfilForm,
    UtilisateurInfoForm,
)
from .models import DemandePassagePro, Profil, Utilisateur

logger = logging.getLogger(__name__)


def home(request):
    if request.user.is_authenticated:
        return redirect('tableau_de_bord_vendeur')
    return redirect('connexion_vendeur')


class InscriptionView(CreateView):
    model = Utilisateur
    form_class = InscriptionForm
    template_name = 'app/layout/inscription.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tableau_de_bord_vendeur')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Évite la création de comptes en masse depuis une même IP (spam, e-mails de bienvenue détournés).
        if throttle.nombre(f'signup:ip:{throttle.client_ip(request)}') >= throttle.SIGNUP_LIMIT_PER_IP:
            self.object = None
            form = self.get_form()
            form.add_error(None, 'Trop de comptes créés depuis cette connexion. Réessayez dans une heure.')
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        throttle.compter(f'signup:ip:{throttle.client_ip(self.request)}', throttle.SIGNUP_WINDOW)
        self.object.backend = 'django.contrib.auth.backends.ModelBackend'
        login(self.request, self.object)
        messages.success(self.request, f'Bienvenue sur Djona, {self.object.prenom} !')
        return response

    def get_success_url(self):
        return reverse('tableau_de_bord_vendeur')


class ConnexionView(LoginView):
    template_name = 'app/layout/connexion.html'
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


# ── Mot de passe oublié ───────────────────────────────────────────────────────
# Limites par fenêtre d'une heure : 3 demandes par adresse e-mail (protège la boîte d'une personne
# visée par du « mail bombing »), 30 par IP. Au-delà, la réponse reste identique mais rien n'est envoyé.
RESET_EMAIL_LIMIT = 3
RESET_IP_LIMIT = 30
RESET_WINDOW = 60 * 60


def _client_ip(request):
    return throttle.client_ip(request)


def _validite_lien():
    """Durée de validité du lien, lisible (« 1 heure », « 30 minutes »), d'après PASSWORD_RESET_TIMEOUT."""
    minutes = max(settings.PASSWORD_RESET_TIMEOUT // 60, 1)
    if minutes % 60 == 0:
        heures = minutes // 60
        return f"{heures} heure{'s' if heures > 1 else ''}"
    return f'{minutes} minutes'


def _within_limit(key, limit, window=RESET_WINDOW):
    """Compte un appel pour `key` ; False si `limit` est dépassée dans la fenêtre."""
    return throttle.compter(key, window) <= limit


class MotDePasseOublieView(PasswordResetView):
    template_name = 'app/layout/mot_de_passe_oublie.html'
    form_class = MotDePasseOublieForm
    success_url = reverse_lazy('mot_de_passe_oublie_envoye')
    email_template_name = 'app/emails/reinitialisation_mdp.txt'
    html_email_template_name = 'app/emails/reinitialisation_mdp.html'
    subject_template_name = 'app/emails/reinitialisation_mdp_sujet.txt'

    @property
    def extra_email_context(self):
        return {'validite': _validite_lien()}

    def _is_limited(self, email):
        email_key = 'pwreset:email:' + hashlib.sha256(email.encode()).hexdigest()
        limited = not _within_limit(email_key, RESET_EMAIL_LIMIT)
        ip = _client_ip(self.request)
        if ip and ip not in ('127.0.0.1', '::1'):  # derrière un proxy sans X-Real-IP : pas de compteur partagé
            limited = not _within_limit('pwreset:ip:' + ip, RESET_IP_LIMIT) or limited
        return limited

    def form_valid(self, form):
        email = form.cleaned_data['email'].strip().lower()
        if self._is_limited(email):
            logger.warning('Mot de passe oublié : trop de demandes (limite atteinte)')
        else:
            form.save(
                use_https=self.request.is_secure() or not settings.DEBUG,
                token_generator=self.token_generator,
                from_email=self.from_email,
                email_template_name=self.email_template_name,
                subject_template_name=self.subject_template_name,
                request=self.request,
                html_email_template_name=self.html_email_template_name,
                extra_email_context=self.extra_email_context,
                domain_override=settings.PASSWORD_RESET_DOMAIN or None,
            )
        # Même réponse dans tous les cas : on ne révèle pas si l'adresse correspond à un compte.
        return HttpResponseRedirect(self.get_success_url())


class MotDePasseOublieEnvoyeView(PasswordResetDoneView):
    template_name = 'app/layout/mot_de_passe_oublie_envoye.html'

    def get_context_data(self, **kwargs):
        return super().get_context_data(validite=_validite_lien(), **kwargs)


class NouveauMotDePasseView(PasswordResetConfirmView):
    template_name = 'app/layout/mot_de_passe_nouveau.html'
    form_class = NouveauMotDePasseForm
    success_url = reverse_lazy('mot_de_passe_reinitialise')


class MotDePasseReinitialiseView(PasswordResetCompleteView):
    template_name = 'app/layout/mot_de_passe_reinitialise.html'


class TableauDeBordVendeurView(LoginRequiredMixin, TemplateView):
    template_name = 'app/layout/tableau_de_bord.html'
    login_url = 'connexion_vendeur'

    def get(self, request, *args, **kwargs):
        if request.user.statut_compte == Utilisateur.StatutCompte.ACTIF and request.user.is_pro_ou_membre:
            return redirect('espace_pro_dashboard')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.statut_compte != Utilisateur.StatutCompte.ACTIF:
            return context

        annonces = Annonce.objects.filter(vendeur=self.request.user)
        context['nb_annonces'] = annonces.count()
        context['nb_brouillons'] = annonces.filter(statut=Annonce.Statut.BROUILLON).count()
        context['nb_en_attente'] = annonces.filter(statut=Annonce.Statut.EN_ATTENTE).count()
        context['nb_publiees'] = annonces.filter(statut=Annonce.Statut.PUBLIEE).count()
        context['nb_refusees'] = annonces.filter(statut=Annonce.Statut.REFUSEE).count()
        context['valeur_publiee'] = (
            annonces.filter(statut=Annonce.Statut.PUBLIEE).aggregate(total=Sum('prix'))['total'] or 0
        )
        avec_photos = annonces.prefetch_related('photos').annotate(nb_photos=Count('photos'))
        context['annonces_a_corriger'] = avec_photos.filter(statut=Annonce.Statut.REFUSEE).order_by('-update_at')[:3]
        context['brouillons'] = avec_photos.filter(statut=Annonce.Statut.BROUILLON).order_by('-update_at')[:3]
        context['annonces_recentes'] = avec_photos.order_by('-update_at')[:5]
        context['min_photos'] = MIN_PHOTOS
        return context


class ProfilVendeurView(LoginRequiredMixin, View):
    template_name = 'app/layout/profil_vendeur.html'
    login_url = 'connexion_vendeur'

    @staticmethod
    def _est_pro(request):
        return request.user.type_compte == Utilisateur.TypeCompte.PROFESSIONNEL

    def _context(self, request, info_form=None, profil_form=None, demande_form=None):
        profil, _ = Profil.objects.get_or_create(user=request.user)
        if info_form is None:
            info_form = UtilisateurInfoForm(user=request.user, initial={
                'nom_complet': f'{request.user.prenom} {request.user.nom}'.strip(),
                'email': request.user.email,
                'telephone': request.user.telephone,
            })
        if profil_form is None:
            profil_form = ProfilForm(instance=profil, inclure_entreprise=self._est_pro(request))

        nb_annonces = Annonce.objects.filter(vendeur=request.user).count()
        derniere_demande = None
        if not self._est_pro(request):
            derniere_demande = request.user.demandes_passage_pro.first()
            if demande_form is None:
                demande_form = DemandePassageProForm()

        return {
            'profil': profil,
            'info_form': info_form,
            'profil_form': profil_form,
            'securite_pourcentage': 100 if profil.two_factor_enabled else 50,
            'nb_annonces': nb_annonces,
            'derniere_demande': derniere_demande,
            'demande_form': demande_form,
        }

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        profil, _ = Profil.objects.get_or_create(user=request.user)
        info_form = UtilisateurInfoForm(request.POST, user=request.user)
        profil_form = ProfilForm(
            request.POST, request.FILES, instance=profil, inclure_entreprise=self._est_pro(request),
        )

        if info_form.is_valid() and profil_form.is_valid():
            with transaction.atomic():
                info_form.save(request.user)
                profil_form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('profil_vendeur')

        messages.error(request, 'Merci de corriger les erreurs ci-dessous.')
        return render(request, self.template_name, self._context(request, info_form, profil_form))


class DemandePassageProView(ProfilVendeurView):
    """Envoi d'une demande de passage en compte professionnel (particuliers
    uniquement, une seule demande en attente à la fois)."""

    def get(self, request):
        return redirect('profil_vendeur')

    def post(self, request):
        if self._est_pro(request):
            messages.info(request, 'Votre compte est déjà un compte professionnel.')
            return redirect('profil_vendeur')
        if request.user.demandes_passage_pro.filter(statut=DemandePassagePro.Statut.EN_ATTENTE).exists():
            messages.info(request, "Vous avez déjà une demande en cours d'examen par l'équipe Djona.")
            return redirect('profil_vendeur')

        form = DemandePassageProForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Merci de corriger les erreurs de votre demande.')
            return render(request, self.template_name, self._context(request, demande_form=form))

        demande = form.save(commit=False)
        demande.utilisateur = request.user
        demande.save()
        messages.success(
            request,
            "Demande envoyée — l'équipe Djona va examiner votre dossier et vous recevrez sa réponse ici.",
        )
        return redirect('profil_vendeur')


class ProfilPasswordChangeView(LoginRequiredMixin, View):
    login_url = 'connexion_vendeur'

    def post(self, request):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Mot de passe modifié avec succès.')
        else:
            for error_list in form.errors.values():
                messages.error(request, error_list.as_text())
        return redirect('profil_vendeur')


from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, TemplateView

from annonces.forms import MIN_PHOTOS
from annonces.models import Annonce
from .forms import ConnexionForm, DemandePassageProForm, InscriptionForm, ProfilForm, UtilisateurInfoForm
from .models import DemandePassagePro, Profil, Utilisateur


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

    def form_valid(self, form):
        response = super().form_valid(form)
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


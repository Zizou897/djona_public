from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .forms import MAX_PHOTOS, MIN_PHOTOS, AnnonceAdminForm
from .models import (
    AnnonceMirror, AnnoncePhotoMirror, CompteVendeur, DemandePassageProMirror, ProfilMirror, VehicleMirror,
)
from .sync import trigger_public_sync

SYSTEM_VENDOR_EMAIL = 'officiel@djona.tech'
SLA_HEURES = 24
LIMITES_PHOTOS = {'min_photos': MIN_PHOTOS, 'max_photos': MAX_PHOTOS}


def _annoter_sla(annonce, now=None):
    """Ajoute `.heures_attente`/`.sla_depasse` sur une annonce en_attente — objectif de
    réponse < 24h (voir AGENTS.md modération). Ne fait rien pour les autres statuts.
    """
    now = now or timezone.now()
    if annonce.statut == AnnonceMirror.Statut.EN_ATTENTE:
        heures = (now - annonce.created_at).total_seconds() / 3600
        annonce.heures_attente = int(heures)
        annonce.sla_depasse = heures > SLA_HEURES
    else:
        annonce.heures_attente = None
        annonce.sla_depasse = False
    return annonce


class _StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )


class VendeurListView(_StaffRequiredMixin, ListView):
    model = CompteVendeur
    template_name = 'moderation/vendeur_liste.html'
    context_object_name = 'vendeurs'
    STATUTS = {choix[0] for choix in CompteVendeur.StatutCompte.choices}
    TYPES = {choix[0] for choix in CompteVendeur.TypeCompte.choices}

    def get_queryset(self):
        vendeurs = CompteVendeur.objects.using('vendor_db').all()
        statut = self.request.GET.get('statut')
        if statut in self.STATUTS:
            vendeurs = vendeurs.filter(statut_compte=statut)
        type_compte = self.request.GET.get('type')
        if type_compte in self.TYPES:
            vendeurs = vendeurs.filter(type_compte=type_compte)
        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            vendeurs = vendeurs.filter(
                Q(nom__icontains=recherche) | Q(prenom__icontains=recherche)
                | Q(email__icontains=recherche) | Q(telephone__icontains=recherche)
            )

        # en_attente affiché en premier (ordre alphabétique du statut : actif < en_attente < suspendu
        # ne convient pas — tri explicite par priorité de traitement).
        statut_order = {
            CompteVendeur.StatutCompte.EN_ATTENTE: 0,
            CompteVendeur.StatutCompte.ACTIF: 1,
            CompteVendeur.StatutCompte.SUSPENDU: 2,
        }
        vendeurs = list(vendeurs)
        vendeurs.sort(key=lambda v: (statut_order.get(v.statut_compte, 99), v.nom))

        profils = {
            profil.user_id: profil
            for profil in ProfilMirror.objects.using('vendor_db').filter(
                user_id__in=[v.pk for v in vendeurs if v.type_compte == CompteVendeur.TypeCompte.PROFESSIONNEL],
            )
        }
        for vendeur in vendeurs:
            vendeur.profil = profils.get(vendeur.pk)
        return vendeurs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tous = CompteVendeur.objects.using('vendor_db')
        context.update({
            'nb_total': tous.count(),
            'nb_en_attente': tous.filter(statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE).count(),
            'nb_actifs': tous.filter(statut_compte=CompteVendeur.StatutCompte.ACTIF).count(),
            'nb_suspendus': tous.filter(statut_compte=CompteVendeur.StatutCompte.SUSPENDU).count(),
            'statut_actif': self.request.GET.get('statut', '') if self.request.GET.get('statut') in self.STATUTS else '',
            'type_actif': self.request.GET.get('type', '') if self.request.GET.get('type') in self.TYPES else '',
            'recherche': self.request.GET.get('q', ''),
        })
        return context


class _VendeurActionView(_StaffRequiredMixin, View):
    nouveau_statut = None
    message = ''

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        vendeur = get_object_or_404(CompteVendeur.objects.using('vendor_db'), pk=pk)
        vendeur.statut_compte = self.nouveau_statut
        vendeur.save(using='vendor_db', update_fields=['statut_compte'])
        messages.success(request, self.message.format(nom=f'{vendeur.prenom} {vendeur.nom}'))
        # Revenir sur la liste avec les mêmes filtres que ceux d'où vient l'action.
        retour = request.POST.get('next', '')
        if url_has_allowed_host_and_scheme(retour, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(retour)
        return redirect('vendeur_liste')


class VendeurActiverView(_VendeurActionView):
    nouveau_statut = CompteVendeur.StatutCompte.ACTIF
    message = 'Compte de {nom} activé.'


class VendeurSuspendreView(_VendeurActionView):
    nouveau_statut = CompteVendeur.StatutCompte.SUSPENDU
    message = 'Compte de {nom} suspendu.'


class VendeurVerificationDetailView(_StaffRequiredMixin, View):
    """Fiche de revue du dossier entreprise (raison sociale, RCCM,
    justificatif) pour un vendeur professionnel — valider/refuser la
    vérification qui donne le badge « Entreprise vérifiée ».
    """
    template_name = 'moderation/vendeur_verification.html'

    def get(self, request, pk):
        vendeur = get_object_or_404(CompteVendeur.objects.using('vendor_db'), pk=pk)
        profil = ProfilMirror.objects.using('vendor_db').filter(user_id=vendeur.pk).first()
        return render(request, self.template_name, {'vendeur': vendeur, 'profil': profil})


class VendeurValiderEntrepriseView(_StaffRequiredMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        profil = get_object_or_404(ProfilMirror.objects.using('vendor_db'), user_id=pk)
        profil.entreprise_verifiee = True
        profil.save(using='vendor_db', update_fields=['entreprise_verifiee'])
        trigger_public_sync.after_response()
        messages.success(request, 'Entreprise vérifiée.')
        return redirect('vendeur_liste')


class VendeurRefuserEntrepriseView(_StaffRequiredMixin, View):
    """Rejette le justificatif actuel — le vendeur doit en renvoyer un
    nouveau. On supprime le fichier plutôt que de juste repasser
    entreprise_verifiee à False, sinon rien ne distingue « jamais examiné »
    de « examiné et refusé » côté vendeur (même badge « non vérifiée »).
    """
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        profil = get_object_or_404(ProfilMirror.objects.using('vendor_db'), user_id=pk)
        profil.entreprise_verifiee = False
        profil.justificatif_rccm.delete(save=False)
        profil.save(using='vendor_db', update_fields=['entreprise_verifiee', 'justificatif_rccm'])
        trigger_public_sync.after_response()
        messages.success(request, 'Vérification refusée — le vendeur doit envoyer un nouveau justificatif.')
        return redirect('vendeur_liste')


class AnnonceModerationListView(_StaffRequiredMixin, ListView):
    template_name = 'moderation/annonce_liste.html'
    context_object_name = 'annonces'

    TRIS = {
        'prix_croissant': 'prix',
        'prix_decroissant': '-prix',
        'recent': '-created_at',
    }
    STATUTS_VALIDES = {choix[0] for choix in AnnonceMirror.Statut.choices}

    def toutes_les_annonces(self):
        return AnnonceMirror.objects.using('vendor_db').select_related('vendeur')

    def get_queryset(self):
        annonces = self.toutes_les_annonces()

        statut = self.request.GET.get('statut')
        if statut in self.STATUTS_VALIDES:
            annonces = annonces.filter(statut=statut)

        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            annonces = annonces.filter(marque__icontains=recherche) | annonces.filter(modele__icontains=recherche)

        tri = self.TRIS.get(self.request.GET.get('tri'), self.TRIS['recent'])
        annonces = list(annonces.prefetch_related('photos').order_by(tri))
        now = timezone.now()
        for annonce in annonces:
            _annoter_sla(annonce, now)
        return annonces

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = self.toutes_les_annonces()
        context['nb_total'] = toutes.count()
        context['nb_publiees'] = toutes.filter(statut=AnnonceMirror.Statut.PUBLIEE).count()
        context['nb_en_attente'] = toutes.filter(statut=AnnonceMirror.Statut.EN_ATTENTE).count()
        context['nb_refusees'] = toutes.filter(statut=AnnonceMirror.Statut.REFUSEE).count()
        context['statut_actif'] = self.request.GET.get('statut', '')
        context['recherche'] = self.request.GET.get('q', '')
        context['tri_actif'] = self.request.GET.get('tri', 'recent')
        return context


class AnnonceModerationDetailView(_StaffRequiredMixin, View):
    template_name = 'moderation/annonce_detail.html'

    def get(self, request, pk):
        annonce = get_object_or_404(
            AnnonceMirror.objects.using('vendor_db').select_related('vendeur'), pk=pk,
        )
        _annoter_sla(annonce)
        photos = annonce.photos.using('vendor_db').all()
        vehicle = None
        if annonce.statut == AnnonceMirror.Statut.PUBLIEE:
            vehicle = VehicleMirror.objects.using('public_db').filter(source_annonce_id=annonce.pk).first()
        return render(request, self.template_name, {
            'annonce': annonce,
            'photos': photos,
            'vehicle': vehicle,
            'motifs_refus': AnnonceMirror.MotifRefus.choices,
        })


class _AnnonceActionView(_StaffRequiredMixin, View):
    nouveau_statut = None

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def extra_fields(self, request):
        """Champs additionnels à appliquer avec le nouveau statut. Retourner None
        annule l'action (ex : motif de refus manquant/invalide).
        """
        return {}

    def post(self, request, pk):
        annonce = get_object_or_404(AnnonceMirror.objects.using('vendor_db'), pk=pk)
        if annonce.statut == AnnonceMirror.Statut.EN_ATTENTE:
            extra = self.extra_fields(request)
            if extra is None:
                return redirect('annonce_moderation_detail', pk=pk)
            annonce.statut = self.nouveau_statut
            for champ, valeur in extra.items():
                setattr(annonce, champ, valeur)
            annonce.save(using='vendor_db', update_fields=['statut', *extra.keys()])
            if self.nouveau_statut == AnnonceMirror.Statut.PUBLIEE:
                trigger_public_sync.after_response()
        return redirect('annonce_moderation_liste')


class AnnonceValiderView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.PUBLIEE


class AnnonceRefuserView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.REFUSEE
    MOTIFS_VALIDES = {choix[0] for choix in AnnonceMirror.MotifRefus.choices}

    def extra_fields(self, request):
        motif = request.POST.get('motif')
        if motif not in self.MOTIFS_VALIDES:
            messages.error(request, 'Choisissez un motif de refus.')
            return None
        return {'motif_refus': motif}


class _AnnoncePublishActionView(_StaffRequiredMixin, View):
    """Active/désactive l'affichage marketplace d'une annonce déjà validée,
    sans toucher à son statut de modération côté vendor (contrairement à
    Valider/Refuser). Bascule Vehicle.publish côté projet public.
    """
    nouvelle_visibilite = None

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        annonce = get_object_or_404(AnnonceMirror.objects.using('vendor_db'), pk=pk)
        if annonce.statut == AnnonceMirror.Statut.PUBLIEE:
            vehicle = VehicleMirror.objects.using('public_db').filter(source_annonce_id=annonce.pk).first()
            if vehicle:
                vehicle.publish = self.nouvelle_visibilite
                vehicle.save(using='public_db', update_fields=['publish'])
                messages.success(
                    request,
                    'Annonce activée sur le marketplace.' if self.nouvelle_visibilite
                    else 'Annonce désactivée du marketplace.',
                )
            else:
                messages.error(request, "Cette annonce n'a pas encore été synchronisée avec le marketplace.")
        return redirect('annonce_moderation_detail', pk=pk)


class AnnonceActiverMarketplaceView(_AnnoncePublishActionView):
    nouvelle_visibilite = True


class AnnonceDesactiverMarketplaceView(_AnnoncePublishActionView):
    nouvelle_visibilite = False


class AnnonceModifierAdminView(_StaffRequiredMixin, View):
    """Correction directe d'une annonce en_attente par un modérateur — alternative
    au Refuser quand le problème est mineur (coquille, prix, description...).
    """
    template_name = 'moderation/annonce_modifier.html'

    def get_annonce_ou_rediriger(self, request, pk):
        annonce = get_object_or_404(AnnonceMirror.objects.using('vendor_db'), pk=pk)
        if annonce.statut != AnnonceMirror.Statut.EN_ATTENTE:
            messages.info(request, 'Seules les annonces en attente peuvent être modifiées ici.')
            return None, redirect('annonce_moderation_detail', pk=pk)
        return annonce, None

    def get(self, request, pk):
        annonce, early_return = self.get_annonce_ou_rediriger(request, pk)
        if early_return:
            return early_return
        return render(request, self.template_name, {'form': AnnonceAdminForm(instance=annonce), 'annonce': annonce})

    def post(self, request, pk):
        annonce, early_return = self.get_annonce_ou_rediriger(request, pk)
        if early_return:
            return early_return

        form = AnnonceAdminForm(request.POST, request.FILES, instance=annonce)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'annonce': annonce})

        annonce = form.save(commit=False)
        annonce.save(using='vendor_db')
        messages.success(request, 'Annonce mise à jour.')
        return redirect('annonce_moderation_detail', pk=pk)


class AnnonceCreateAdminView(_StaffRequiredMixin, View):
    template_name = 'moderation/annonce_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': AnnonceAdminForm(), **LIMITES_PHOTOS})

    def post(self, request):
        form = AnnonceAdminForm(request.POST, request.FILES, exiger_photos_minimum=True)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, **LIMITES_PHOTOS})

        vendeur = CompteVendeur.objects.using('vendor_db').filter(email=SYSTEM_VENDOR_EMAIL).first()
        if vendeur is None:
            messages.error(
                request,
                "Le compte vendeur système (officiel@djona.tech) n'existe pas — "
                "lancez `manage.py create_system_vendor` côté projet vendor.",
            )
            return render(request, self.template_name, {'form': form, **LIMITES_PHOTOS})

        # created_at/update_at n'ont pas d'auto_now(_add) sur ce mirror (ils
        # viennent de app.Convention côté vendor, jamais appliqué ici) — à
        # renseigner explicitement, seul cas où ce mirror sert à créer une ligne.
        now = timezone.now()
        annonce = form.save(commit=False)
        annonce.vendeur_id = vendeur.pk
        annonce.statut = AnnonceMirror.Statut.PUBLIEE
        annonce.publish = True
        annonce.created_at = now
        annonce.update_at = now
        annonce.save(using='vendor_db')

        for index, photo in enumerate(request.FILES.getlist('photos')):
            AnnoncePhotoMirror.objects.using('vendor_db').create(annonce=annonce, image=photo, ordre=index)

        trigger_public_sync.after_response()
        messages.success(request, 'Annonce créée et publiée sur le marketplace.')
        return redirect('annonce_moderation_liste')


class DemandeProListView(_StaffRequiredMixin, View):
    """Demandes de passage en compte professionnel envoyées par des vendeurs
    particuliers — en attente d'abord, puis les plus récentes."""
    template_name = 'moderation/demande_pro_liste.html'
    STATUTS = {choix[0] for choix in DemandePassageProMirror.Statut.choices}

    def get(self, request):
        toutes = DemandePassageProMirror.objects.using('vendor_db')
        statut = request.GET.get('statut', '')
        demandes = toutes.filter(statut=statut) if statut in self.STATUTS else toutes
        demandes = demandes.select_related('utilisateur').annotate(
            priorite=Case(
                When(statut=DemandePassageProMirror.Statut.EN_ATTENTE, then=Value(0)),
                default=Value(1), output_field=IntegerField(),
            ),
        ).order_by('priorite', '-created_at')
        compteurs = {
            valeur: toutes.filter(statut=valeur).count() for valeur in self.STATUTS
        }
        return render(request, self.template_name, {
            'demandes': demandes,
            'statut_actif': statut if statut in self.STATUTS else '',
            'nb_total': toutes.count(),
            'nb_en_attente': compteurs[DemandePassageProMirror.Statut.EN_ATTENTE],
            'nb_acceptees': compteurs[DemandePassageProMirror.Statut.ACCEPTEE],
            'nb_refusees': compteurs[DemandePassageProMirror.Statut.REFUSEE],
        })


class DemandeProDetailView(_StaffRequiredMixin, View):
    template_name = 'moderation/demande_pro_detail.html'

    def get(self, request, pk):
        demande = get_object_or_404(
            DemandePassageProMirror.objects.using('vendor_db').select_related('utilisateur'), pk=pk,
        )
        autres_demandes = (
            DemandePassageProMirror.objects.using('vendor_db')
            .filter(utilisateur_id=demande.utilisateur_id).exclude(pk=demande.pk)
        )
        return render(request, self.template_name, {'demande': demande, 'autres_demandes': autres_demandes})


class _DemandeProTraitementMixin(_StaffRequiredMixin):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def demande_en_attente(self, request, pk):
        demande = get_object_or_404(DemandePassageProMirror.objects.using('vendor_db'), pk=pk)
        if demande.statut != DemandePassageProMirror.Statut.EN_ATTENTE:
            messages.info(request, 'Cette demande a déjà été traitée.')
            return None
        return demande


class DemandeProAccepterView(_DemandeProTraitementMixin, View):
    """Le compte passe professionnel et l'entreprise est marquée vérifiée en
    une seule action : l'équipe a examiné le RCCM pour accepter la demande."""

    def post(self, request, pk):
        demande = self.demande_en_attente(request, pk)
        if demande is None:
            return redirect('demande_pro_detail', pk=pk)

        with transaction.atomic(using='vendor_db'):
            compte = CompteVendeur.objects.using('vendor_db').select_for_update().get(pk=demande.utilisateur_id)
            compte.type_compte = CompteVendeur.TypeCompte.PROFESSIONNEL
            compte.save(using='vendor_db', update_fields=['type_compte'])

            profil, _ = ProfilMirror.objects.using('vendor_db').get_or_create(user_id=compte.pk)
            profil.raison_sociale = demande.raison_sociale
            profil.numero_rccm = demande.numero_rccm
            profil.adresse = demande.adresse
            profil.justificatif_rccm.name = demande.justificatif_rccm.name
            profil.entreprise_verifiee = True
            profil.save(using='vendor_db', update_fields=[
                'raison_sociale', 'numero_rccm', 'adresse', 'justificatif_rccm', 'entreprise_verifiee',
            ])

            demande.statut = DemandePassageProMirror.Statut.ACCEPTEE
            demande.traitee_le = timezone.now()
            demande.save(using='vendor_db', update_fields=['statut', 'traitee_le'])

        trigger_public_sync.after_response()
        messages.success(request, f'{compte.prenom} {compte.nom} est maintenant un compte professionnel vérifié.')
        return redirect('demande_pro_liste')


class DemandeProRefuserView(_DemandeProTraitementMixin, View):
    def post(self, request, pk):
        demande = self.demande_en_attente(request, pk)
        if demande is None:
            return redirect('demande_pro_detail', pk=pk)

        motif = request.POST.get('motif_refus', '').strip()
        if not motif:
            messages.error(request, 'Indiquez le motif du refus : il sera affiché au vendeur.')
            return redirect('demande_pro_detail', pk=pk)

        demande.statut = DemandePassageProMirror.Statut.REFUSEE
        demande.motif_refus = motif
        demande.traitee_le = timezone.now()
        demande.save(using='vendor_db', update_fields=['statut', 'motif_refus', 'traitee_le'])
        messages.success(request, 'Demande refusée — le vendeur verra le motif dans ses paramètres.')
        return redirect('demande_pro_liste')

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .forms import AnnonceAdminForm
from .models import AnnonceMirror, AnnoncePhotoMirror, CompteVendeur, VehicleMirror
from .sync import trigger_public_sync

SYSTEM_VENDOR_EMAIL = 'officiel@djona.tech'


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


class _VendeurActionView(_StaffRequiredMixin, View):
    nouveau_statut = None

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
        return annonces.order_by(tri)

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
        photos = annonce.photos.using('vendor_db').all()
        vehicle = None
        if annonce.statut == AnnonceMirror.Statut.PUBLIEE:
            vehicle = VehicleMirror.objects.using('public_db').filter(source_annonce_id=annonce.pk).first()
        return render(request, self.template_name, {'annonce': annonce, 'photos': photos, 'vehicle': vehicle})


class _AnnonceActionView(_StaffRequiredMixin, View):
    nouveau_statut = None

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


class AnnonceCreateAdminView(_StaffRequiredMixin, View):
    template_name = 'moderation/annonce_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': AnnonceAdminForm()})

    def post(self, request):
        form = AnnonceAdminForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        vendeur = CompteVendeur.objects.using('vendor_db').filter(email=SYSTEM_VENDOR_EMAIL).first()
        if vendeur is None:
            messages.error(
                request,
                "Le compte vendeur système (officiel@djona.tech) n'existe pas — "
                "lancez `manage.py create_system_vendor` côté projet vendor.",
            )
            return render(request, self.template_name, {'form': form})

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

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .forms import AnnonceForm
from .models import Annonce, AnnoncePhoto
from .sync import trigger_public_sync


class _CompteActifRequisMixin(LoginRequiredMixin):
    login_url = 'connexion_vendeur'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.statut_compte != request.user.StatutCompte.ACTIF:
            if request.user.statut_compte == request.user.StatutCompte.SUSPENDU:
                messages.error(request, "Votre compte est suspendu. Contactez notre support pour plus d'informations.")
            else:
                messages.info(request, "Votre compte doit être activé pour gérer des annonces.")
            return redirect('tableau_de_bord_vendeur')
        return super().dispatch(request, *args, **kwargs)


class AnnonceCreateView(_CompteActifRequisMixin, View):
    template_name = 'annonces/annonce_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': AnnonceForm()})

    def post(self, request):
        form = AnnonceForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        with transaction.atomic():
            annonce = form.save(commit=False)
            annonce.vendeur = request.user
            action = request.POST.get('action')
            annonce.statut = Annonce.Statut.EN_ATTENTE if action == 'soumettre' else Annonce.Statut.BROUILLON
            annonce.save()

            for index, photo in enumerate(request.FILES.getlist('photos')):
                AnnoncePhoto.objects.create(annonce=annonce, image=photo, ordre=index)

        messages.success(request, 'Annonce enregistrée avec succès.')
        return redirect(reverse('mes_annonces'))


class MesAnnoncesListView(_CompteActifRequisMixin, ListView):
    model = Annonce
    template_name = 'annonces/mes_annonces.html'
    context_object_name = 'annonces'

    TRIS = {
        'prix_croissant': 'prix',
        'prix_decroissant': '-prix',
        'recent': '-created_at',
    }
    STATUTS_VALIDES = {choix[0] for choix in Annonce.Statut.choices}

    def toutes_les_annonces(self):
        return Annonce.objects.filter(vendeur=self.request.user)

    def get_queryset(self):
        annonces = self.toutes_les_annonces()

        statut = self.request.GET.get('statut')
        if statut in self.STATUTS_VALIDES:
            annonces = annonces.filter(statut=statut)

        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            annonces = annonces.filter(Q(marque__icontains=recherche) | Q(modele__icontains=recherche))

        tri = self.TRIS.get(self.request.GET.get('tri'), self.TRIS['recent'])
        return annonces.order_by(tri)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = self.toutes_les_annonces()
        context['nb_total'] = toutes.count()
        context['nb_publiees'] = toutes.filter(statut=Annonce.Statut.PUBLIEE).count()
        context['nb_en_attente'] = toutes.filter(statut=Annonce.Statut.EN_ATTENTE).count()
        context['nb_refusees'] = toutes.filter(statut=Annonce.Statut.REFUSEE).count()
        context['statut_actif'] = self.request.GET.get('statut', '')
        context['recherche'] = self.request.GET.get('q', '')
        context['tri_actif'] = self.request.GET.get('tri', 'recent')
        return context


class AnnoncePublierView(_CompteActifRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        annonce = get_object_or_404(Annonce, pk=pk, vendeur=request.user)
        if annonce.statut == Annonce.Statut.BROUILLON:
            annonce.statut = Annonce.Statut.EN_ATTENTE
            annonce.save(update_fields=['statut'])
            messages.success(request, 'Annonce soumise pour validation.')
        return redirect('mes_annonces')


class AnnonceUpdateView(_CompteActifRequisMixin, View):
    template_name = 'annonces/annonce_form_edition.html'
    statuts_modifiables = (Annonce.Statut.BROUILLON, Annonce.Statut.REFUSEE, Annonce.Statut.PUBLIEE)

    def get_annonce(self, request, pk):
        return get_object_or_404(Annonce, pk=pk, vendeur=request.user)

    def get_annonce_ou_rediriger(self, request, pk):
        """Retourne (annonce, None) si modifiable, ou (None, redirect_response) sinon."""
        annonce = self.get_annonce(request, pk)
        if annonce.statut not in self.statuts_modifiables:
            messages.info(request, "Cette annonce ne peut plus être modifiée pour le moment.")
            return None, redirect('mes_annonces')
        return annonce, None

    def get(self, request, pk):
        annonce, early_return = self.get_annonce_ou_rediriger(request, pk)
        if early_return:
            return early_return
        return render(request, self.template_name, {'form': AnnonceForm(instance=annonce), 'annonce': annonce})

    def post(self, request, pk):
        annonce, early_return = self.get_annonce_ou_rediriger(request, pk)
        if early_return:
            return early_return

        etait_refusee = annonce.statut == Annonce.Statut.REFUSEE
        etait_publiee = annonce.statut == Annonce.Statut.PUBLIEE

        form = AnnonceForm(request.POST, request.FILES, instance=annonce)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'annonce': annonce})

        with transaction.atomic():
            annonce = form.save(commit=False)
            annonce.statut = Annonce.Statut.BROUILLON
            annonce.motif_refus = ''
            annonce.save()

        if etait_publiee:
            # Elle disparaît du marketplace immédiatement, sans attendre la
            # prochaine validation admin (qui déclenche aussi une synchro).
            trigger_public_sync.after_response()
            messages.success(
                request,
                "Annonce mise à jour et retirée du marketplace — repassez-la en attente de "
                "validation pour qu'elle soit de nouveau visible.",
            )
        elif etait_refusee:
            messages.success(request, "Annonce mise à jour et repassée en brouillon — pensez à la republier.")
        else:
            messages.success(request, 'Annonce mise à jour.')
        return redirect('mes_annonces')


class AnnonceDeleteView(_CompteActifRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        annonce = get_object_or_404(Annonce, pk=pk, vendeur=request.user)
        etait_publiee = annonce.statut == Annonce.Statut.PUBLIEE
        annonce.delete()

        if etait_publiee:
            # Le véhicule correspondant doit disparaître du marketplace tout de
            # suite, sans attendre la prochaine validation admin.
            trigger_public_sync.after_response()

        messages.success(request, 'Annonce supprimée.')
        return redirect('mes_annonces')

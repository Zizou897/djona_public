from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from annonces.models import Annonce
from app.models import Utilisateur

from .forms import MembreEquipeForm, ProspectForm
from .models import MembreEquipe, Prospect


class _EspaceProRequisMixin(LoginRequiredMixin):
    """Résout le contexte pro (titulaire ou membre d'équipe rattaché) et
    l'expose sur `self.compte_pro`/`self.role`/`self.est_proprietaire`.

    `role_requis` restreint en plus l'accès à la vue :
    - None : tout membre actif (lecture seule incluse) ;
    - MembreEquipe.Role.GESTIONNAIRE : lecture seule exclue ;
    - 'proprietaire' : seul le titulaire du compte entreprise (jamais un membre délégué).
    """

    login_url = 'connexion_vendeur'
    role_requis = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        if request.user.statut_compte != Utilisateur.StatutCompte.ACTIF:
            messages.info(request, "Votre compte doit être activé pour accéder à l'espace professionnel.")
            return redirect('tableau_de_bord_vendeur')

        if request.user.type_compte == Utilisateur.TypeCompte.PROFESSIONNEL:
            self.compte_pro = request.user
            self.role = MembreEquipe.Role.GESTIONNAIRE
            self.est_proprietaire = True
        else:
            rattachement = getattr(request.user, 'rattachement_pro', None)
            if not (rattachement and rattachement.actif):
                messages.info(request, "L'espace professionnel est réservé aux comptes entreprise.")
                return redirect('tableau_de_bord_vendeur')
            self.compte_pro = rattachement.compte_pro
            self.role = rattachement.role
            self.est_proprietaire = False

        if self.role_requis == 'proprietaire' and not self.est_proprietaire:
            messages.error(request, 'Seul le titulaire du compte entreprise peut gérer l\'équipe.')
            return redirect('espace_pro_equipe')
        if self.role_requis == MembreEquipe.Role.GESTIONNAIRE and self.role == MembreEquipe.Role.LECTURE_SEULE:
            messages.error(request, "Votre rôle « Lecture seule » ne permet pas cette action.")
            return redirect('espace_pro_prospects')

        return super().dispatch(request, *args, **kwargs)

    def contexte_pro(self, **extra):
        return {
            'compte_pro': self.compte_pro,
            'role': self.role,
            'est_proprietaire': self.est_proprietaire,
            **extra,
        }


class EspaceProDashboardView(_EspaceProRequisMixin, View):
    def get(self, request):
        annonces = Annonce.objects.filter(vendeur=self.compte_pro)
        prospects = Prospect.objects.filter(compte_pro=self.compte_pro)
        valeur_stock = annonces.filter(statut=Annonce.Statut.PUBLIEE).aggregate(total=Sum('prix'))['total'] or 0

        context = self.contexte_pro(
            nb_annonces=annonces.count(),
            nb_publiees=annonces.filter(statut=Annonce.Statut.PUBLIEE).count(),
            nb_en_attente=annonces.filter(statut=Annonce.Statut.EN_ATTENTE).count(),
            nb_brouillons=annonces.filter(statut=Annonce.Statut.BROUILLON).count(),
            valeur_stock=valeur_stock,
            nb_membres=MembreEquipe.objects.filter(compte_pro=self.compte_pro, actif=True).count(),
            nb_prospects_nouveaux=prospects.filter(statut=Prospect.Statut.NOUVEAU).count(),
            nb_prospects_en_cours=prospects.filter(
                statut__in=[Prospect.Statut.CONTACTE, Prospect.Statut.NEGOCIATION],
            ).count(),
            prospects_recents=prospects.select_related('annonce')[:5],
            annonces_recentes=annonces.prefetch_related('photos').order_by('-created_at')[:4],
        )
        return render(request, 'pro/dashboard.html', context)


class EquipeListView(_EspaceProRequisMixin, View):
    def get(self, request):
        membres = MembreEquipe.objects.filter(compte_pro=self.compte_pro).select_related('membre')
        return render(request, 'pro/equipe.html', self.contexte_pro(membres=membres, form=MembreEquipeForm()))


class EquipeInviterView(_EspaceProRequisMixin, View):
    role_requis = 'proprietaire'

    def post(self, request):
        form = MembreEquipeForm(request.POST)
        if form.is_valid():
            form.save(compte_pro=self.compte_pro)
            messages.success(request, 'Membre ajouté à votre équipe.')
            return redirect('espace_pro_equipe')

        messages.error(request, 'Merci de corriger les erreurs ci-dessous.')
        membres = MembreEquipe.objects.filter(compte_pro=self.compte_pro).select_related('membre')
        return render(request, 'pro/equipe.html', self.contexte_pro(membres=membres, form=form))


class EquipeToggleActifView(_EspaceProRequisMixin, View):
    role_requis = 'proprietaire'

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        membre = get_object_or_404(MembreEquipe, pk=pk, compte_pro=self.compte_pro)
        membre.actif = not membre.actif
        membre.save(update_fields=['actif'])
        messages.success(request, 'Accès réactivé.' if membre.actif else 'Accès suspendu.')
        return redirect('espace_pro_equipe')


class EquipeRetirerView(_EspaceProRequisMixin, View):
    role_requis = 'proprietaire'

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        membre = get_object_or_404(MembreEquipe, pk=pk, compte_pro=self.compte_pro)
        membre.delete()
        messages.success(request, "Membre retiré de l'équipe — son compte de connexion reste actif mais perd l'accès à ce stock.")
        return redirect('espace_pro_equipe')


class _ProspectListMixin:
    def _statuts_compteurs(self):
        return [
            (valeur, libelle, Prospect.objects.filter(compte_pro=self.compte_pro, statut=valeur).count())
            for valeur, libelle in Prospect.Statut.choices
        ]


class ProspectListView(_ProspectListMixin, _EspaceProRequisMixin, View):
    def get(self, request):
        prospects = Prospect.objects.filter(compte_pro=self.compte_pro).select_related('annonce')
        statut = request.GET.get('statut', '')
        if statut in Prospect.Statut.values:
            prospects = prospects.filter(statut=statut)

        return render(request, 'pro/prospects.html', self.contexte_pro(
            prospects=prospects,
            form=ProspectForm(compte_pro=self.compte_pro),
            statut_actif=statut,
            statuts_compteurs=self._statuts_compteurs(),
        ))


class ProspectCreateView(_ProspectListMixin, _EspaceProRequisMixin, View):
    role_requis = MembreEquipe.Role.GESTIONNAIRE

    def post(self, request):
        form = ProspectForm(request.POST, compte_pro=self.compte_pro)
        if form.is_valid():
            prospect = form.save(commit=False)
            prospect.compte_pro = self.compte_pro
            prospect.save()
            messages.success(request, 'Prospect ajouté.')
            return redirect('espace_pro_prospects')

        messages.error(request, 'Merci de corriger les erreurs ci-dessous.')
        prospects = Prospect.objects.filter(compte_pro=self.compte_pro).select_related('annonce')
        return render(request, 'pro/prospects.html', self.contexte_pro(
            prospects=prospects,
            form=form,
            statut_actif='',
            statuts_compteurs=self._statuts_compteurs(),
        ))


class ProspectUpdateStatutView(_EspaceProRequisMixin, View):
    role_requis = MembreEquipe.Role.GESTIONNAIRE

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        prospect = get_object_or_404(Prospect, pk=pk, compte_pro=self.compte_pro)
        statut = request.POST.get('statut')
        if statut in Prospect.Statut.values:
            prospect.statut = statut
            prospect.notes = request.POST.get('notes', prospect.notes)
            prospect.save(update_fields=['statut', 'notes', 'update_at'])
            messages.success(request, 'Prospect mis à jour.')
        return redirect('espace_pro_prospects')


class ProspectDeleteView(_EspaceProRequisMixin, View):
    role_requis = MembreEquipe.Role.GESTIONNAIRE

    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        prospect = get_object_or_404(Prospect, pk=pk, compte_pro=self.compte_pro)
        prospect.delete()
        messages.success(request, 'Prospect supprimé.')
        return redirect('espace_pro_prospects')

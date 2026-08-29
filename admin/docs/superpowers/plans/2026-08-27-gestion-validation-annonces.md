# Gestion et validation des annonces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un vendeur au compte `actif` crée, édite et publie ses propres annonces
véhicule ; le dashboard admin liste les annonces soumises (`en_attente`) et permet de
les valider ou de les refuser.

**Architecture:** Nouvelle app `annonces` côté vendor (modèles réels, propriétaire des
données), avec un wizard de création à 4 étapes adapté de celui déjà construit côté
admin (sans étape de sélection de vendeur — `vendeur = request.user`). Côté admin,
modèles miroirs `managed=False` (`AnnonceMirror`, `AnnoncePhotoMirror`) dans l'app
`moderation` déjà créée par le plan précédent, utilisant la connexion `vendor_db`.
L'ancienne app `annonces` côté admin (modèle `Vendeur` sans authentification, wizard de
création pour un tiers) est retirée à la fin de ce plan.

**Tech Stack:** Django 5.0.14, MySQL local, Pillow (déjà en dépendance des deux
projets).

**Prérequis :** Ce plan suppose que
`docs/superpowers/plans/2026-08-27-activation-compte-vendeur.md` est déjà implémenté
(champ `statut_compte`, connexion `vendor_db`, app `moderation` avec `CompteVendeur`
et la liste des vendeurs).

**Référence design complet :** `docs/superpowers/specs/2026-08-27-workflow-vendeur-admin-design.md`

---

## Contexte pour l'exécutant

Mêmes deux projets Django séparés que le plan précédent (`vendor/core/src`,
`admin/core/src`), chacun avec son propre venv. Toute commande Django se lance depuis
le dossier `src/` du projet concerné avec l'exécutable Python de CE projet.

**Important — `manage.py test` côté admin nécessite `--keepdb` :** comme découvert et
corrigé au plan précédent (Task 3-4), la connexion `vendor_db` pointe, en mode test,
vers une base dédiée `djona_vendor_test`, peuplée manuellement en rejouant les
migrations du projet vendor dessus — jamais par le test-runner Django lui-même (modèles
miroirs `managed=False`). Sans `--keepdb`, Django supprime et recrée cette base à
chaque run (vide). Donc partout dans ce plan où une commande dit
`../venv/Scripts/python.exe manage.py test` **pour le projet admin**, lancer en réalité
`../venv/Scripts/python.exe manage.py test --keepdb`. Côté vendor, `--keepdb` n'est pas
nécessaire.

**Important — resynchroniser `djona_vendor_test` après la Task 1 de ce plan :** la
Task 1 ajoute une nouvelle app `annonces` côté vendor avec sa propre migration. Une
fois cette migration appliquée sur la vraie base `djona_vendor`, il faut aussi la
rejouer sur `djona_vendor_test` avant que la Task 7 (modèles miroirs `AnnonceMirror`)
puisse fonctionner :
```bash
cd vendor/core/src
MYSQL_DB=djona_vendor_test ../venv/Scripts/python.exe manage.py migrate
```
(Cette commande utilise une variable d'environnement pour pointer temporairement vers
la base de test dédiée, sans modifier `vendor/core/.env`.)

Dans ce plan, chaque vue vendor scope systématiquement ses requêtes sur
`request.user` — un vendeur ne doit jamais pouvoir lire ou modifier l'annonce d'un
autre vendeur.

---

## Task 1: Modèles `Annonce` / `AnnoncePhoto` (vendor)

**Files:**
- Create: `vendor/core/src/annonces/__init__.py`
- Create: `vendor/core/src/annonces/apps.py`
- Create: `vendor/core/src/annonces/models.py`
- Create: `vendor/core/src/annonces/tests/__init__.py`
- Create: `vendor/core/src/annonces/tests/test_models.py`
- Create: `vendor/core/src/annonces/migrations/__init__.py` (générée)
- Create: `vendor/core/src/annonces/migrations/0001_initial.py` (générée)
- Modify: `vendor/core/src/core/settings.py` (`LOCAL_APPS`)
- Modify: `vendor/core/requirements.txt`

- [ ] **Step 1: Créer le squelette de l'app**

Run:
```bash
cd vendor/core/src
../venv/Scripts/python.exe manage.py startapp annonces
rm annonces/tests.py
mkdir annonces/tests
touch annonces/tests/__init__.py
```

- [ ] **Step 2: Déclarer l'app dans les settings**

Dans `vendor/core/src/core/settings.py`, `LOCAL_APPS` est actuellement :

```python
LOCAL_APPS = [
    'app',
]
```

Remplacer par :

```python
LOCAL_APPS = [
    'app',
    'annonces',
]
```

- [ ] **Step 3: Ajouter Pillow aux dépendances**

Vérifier que `vendor/core/requirements.txt` contient déjà `pillow==12.3.0` (c'est le
cas — copié du scaffold `django-init` initial). `ImageField` (utilisé par
`AnnoncePhoto`) en a besoin pour la validation d'image. Aucune action si déjà présent ;
sinon l'ajouter et lancer `../venv/Scripts/python.exe -m pip install -r requirements.txt`.

- [ ] **Step 4: Écrire le test qui échoue**

Contenu complet de `vendor/core/src/annonces/tests/test_models.py` :

```python
from django.test import TestCase

from app.models import Utilisateur
from annonces.models import Annonce, AnnoncePhoto


class AnnonceModelTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405',
        )

    def annonce_data(self, **overrides):
        data = {
            'vendeur': self.vendeur,
            'marque': 'Toyota',
            'modele': 'Corolla',
            'annee': 2019,
            'prix': 8500000,
            'kilometrage': 45000,
            'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE,
            'couleur': 'Gris',
            'description': 'Très bon état, entretien à jour.',
        }
        data.update(overrides)
        return data

    def test_statut_par_defaut_est_brouillon(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertFalse(annonce.publish)

    def test_publish_se_synchronise_avec_statut_publiee(self):
        annonce = Annonce.objects.create(**self.annonce_data(statut=Annonce.Statut.PUBLIEE))
        self.assertTrue(annonce.publish)
        annonce.statut = Annonce.Statut.REFUSEE
        annonce.save()
        self.assertFalse(annonce.publish)

    def test_suppression_du_vendeur_supprime_ses_annonces(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        annonce_pk = annonce.pk
        self.vendeur.delete()
        self.assertFalse(Annonce.objects.filter(pk=annonce_pk).exists())

    def test_photo_ordonnee_par_ordre(self):
        annonce = Annonce.objects.create(**self.annonce_data())
        AnnoncePhoto.objects.create(annonce=annonce, image='annonces/test2.jpg', ordre=1)
        AnnoncePhoto.objects.create(annonce=annonce, image='annonces/test1.jpg', ordre=0)
        photos = list(annonce.photos.all())
        self.assertEqual(photos[0].ordre, 0)
        self.assertEqual(photos[1].ordre, 1)
```

- [ ] **Step 5: Vérifier que le test échoue**

Run: `../venv/Scripts/python.exe manage.py test annonces -v 2`
Expected: `ModuleNotFoundError: No module named 'annonces.models'`

- [ ] **Step 6: Écrire le modèle**

Contenu complet de `vendor/core/src/annonces/models.py` :

```python
from django.conf import settings
from django.db import models

from app.models import Convention


class Annonce(Convention):
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE = 'en_attente', 'En attente'
        PUBLIEE = 'publiee', 'Publiée'
        REFUSEE = 'refusee', 'Refusée'

    class Carburant(models.TextChoices):
        ESSENCE = 'essence', 'Essence'
        DIESEL = 'diesel', 'Diesel'
        HYBRIDE = 'hybride', 'Hybride'
        ELECTRIQUE = 'electrique', 'Électrique'

    class BoiteVitesses(models.TextChoices):
        MANUELLE = 'manuelle', 'Manuelle'
        AUTOMATIQUE = 'automatique', 'Automatique'

    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annonces')
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20, choices=Carburant.choices)
    boite_vitesses = models.CharField(max_length=20, choices=BoiteVitesses.choices)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, db_index=True)

    class Meta:
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'

    def save(self, *args, **kwargs):
        # Ne se synchronise qu'à .save() — un .update()/.bulk_create() en masse
        # contournerait ceci et laisserait `publish` obsolète. Toujours passer par
        # .save() sur une instance individuelle.
        self.publish = self.statut == self.Statut.PUBLIEE
        super().save(*args, **kwargs)


class AnnoncePhoto(models.Model):
    annonce = models.ForeignKey(Annonce, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='annonces/%Y/%m/')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'annonce_photos'
        ordering = ['ordre']

    def __str__(self):
        return f'Photo #{self.ordre} — {self.annonce}'
```

- [ ] **Step 7: Générer et appliquer la migration**

Run:
```bash
../venv/Scripts/python.exe manage.py makemigrations annonces
../venv/Scripts/python.exe manage.py migrate
```
Expected : `Migrations for 'annonces': ... - Create model Annonce - Create model
AnnoncePhoto`, puis `Applying annonces.0001_initial... OK`.

- [ ] **Step 8: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test annonces -v 2`
Expected: PASS (4 tests)

- [ ] **Step 9: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (26 tests : 22 existants + 4 nouveaux).

- [ ] **Step 10: Commit**

```bash
cd vendor/core
git add -A src/annonces src/core/settings.py
git commit -m "feat(annonces): ajoute les modèles Annonce et AnnoncePhoto (vendor)"
```

---

## Task 2: `AnnonceForm` (vendor, simplifié — pas de sélection de vendeur)

**Files:**
- Create: `vendor/core/src/annonces/forms.py`
- Create: `vendor/core/src/annonces/tests/test_forms.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Contenu complet de `vendor/core/src/annonces/tests/test_forms.py` :

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from annonces.forms import AnnonceForm
from annonces.models import Annonce

# Le plus petit PNG valide possible (1x1 pixel transparent), en octets bruts —
# nécessaire pour que la validation Pillow (forms.ImageField().clean()) accepte le
# fichier comme une vraie image.
PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00'
    b'\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class AnnonceFormTest(TestCase):
    def valid_data(self, **overrides):
        data = {
            'marque': 'Toyota',
            'modele': 'Corolla',
            'annee': 2019,
            'prix': 8500000,
            'kilometrage': 45000,
            'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE,
            'couleur': 'Gris',
            'description': 'Très bon état.',
        }
        data.update(overrides)
        return data

    def test_valide_sans_photo(self):
        form = AnnonceForm(data=self.valid_data(), files=MultiValueDict())
        self.assertTrue(form.is_valid(), form.errors)

    def test_valide_avec_photos(self):
        photo = SimpleUploadedFile('photo.png', PNG_1PX, content_type='image/png')
        files = MultiValueDict({'photos': [photo]})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejette_plus_de_8_photos(self):
        photos = [
            SimpleUploadedFile(f'photo{i}.png', PNG_1PX, content_type='image/png')
            for i in range(9)
        ]
        files = MultiValueDict({'photos': photos})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertFalse(form.is_valid())

    def test_rejette_fichier_non_image(self):
        fichier = SimpleUploadedFile('doc.txt', b'pas une image', content_type='text/plain')
        files = MultiValueDict({'photos': [fichier]})
        form = AnnonceForm(data=self.valid_data(), files=files)
        self.assertFalse(form.is_valid())

    def test_ne_contient_pas_de_champ_vendeur(self):
        form = AnnonceForm()
        self.assertNotIn('vendeur', form.fields)
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_forms -v 2`
Expected: `ModuleNotFoundError: No module named 'annonces.forms'`

- [ ] **Step 3: Écrire le formulaire**

Contenu complet de `vendor/core/src/annonces/forms.py` :

```python
from django import forms

from .models import Annonce


class AnnonceForm(forms.ModelForm):
    class Meta:
        model = Annonce
        fields = [
            'marque', 'modele', 'annee', 'prix',
            'kilometrage', 'carburant', 'boite_vitesses', 'couleur',
            'description',
        ]

    def clean(self):
        cleaned_data = super().clean()
        errors = []

        photos = self.files.getlist('photos')
        if len(photos) > 8:
            errors.append("Vous ne pouvez pas ajouter plus de 8 photos.")
        else:
            # AnnoncePhoto est créé directement par la vue via .objects.create(),
            # sans passer par un ModelForm — donc sans la validation Pillow que
            # forms.ImageField apporte normalement. On la déclenche ici pour
            # rejeter les fichiers non-image avant la sauvegarde.
            image_field = forms.ImageField()
            for photo in photos:
                try:
                    image_field.clean(photo)
                except forms.ValidationError:
                    errors.append(f"« {photo.name} » n'est pas une image valide.")

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_data
```

(Pas de champ `vendeur` : la vue assigne `vendeur = request.user` directement, jamais
depuis les données du formulaire.)

- [ ] **Step 4: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test annonces.tests.test_forms -v 2`
Expected: PASS (5 tests)

- [ ] **Step 5: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (31 tests).

- [ ] **Step 6: Commit**

```bash
cd vendor/core
git add -A src/annonces/forms.py src/annonces/tests/test_forms.py
git commit -m "feat(annonces): ajoute AnnonceForm (vendor, sans sélection de vendeur)"
```

---

## Task 3: Wizard de création d'annonce (vendor)

**Files:**
- Create: `vendor/core/src/annonces/views.py`
- Create: `vendor/core/src/annonces/urls.py`
- Create: `vendor/core/src/templates/annonces/annonce_form.html`
- Create: `vendor/core/src/annonces/tests/test_views.py`
- Modify: `vendor/core/src/core/urls.py`
- Modify: `vendor/core/src/templates/app/layout/tableau_de_bord.html`

- [ ] **Step 1: Écrire les tests qui échouent**

Contenu complet de `vendor/core/src/annonces/tests/test_views.py` :

```python
from django.test import TestCase
from django.urls import reverse

from app.models import Utilisateur
from annonces.models import Annonce


class AnnonceCreateViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def annonce_data(self, **overrides):
        data = {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 8500000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état.',
        }
        data.update(overrides)
        return data

    def test_requiert_authentification(self):
        self.client.logout()
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('annonce_creer')}")

    def test_compte_en_attente_ne_peut_pas_creer(self):
        self.vendeur.statut_compte = Utilisateur.StatutCompte.EN_ATTENTE
        self.vendeur.save()
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, reverse('tableau_de_bord_vendeur'))

    def test_creation_sans_action_sauvegarde_en_brouillon(self):
        response = self.client.post(reverse('annonce_creer'), self.annonce_data(action='enregistrer'))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)

    def test_creation_avec_action_soumettre_passe_en_attente(self):
        response = self.client.post(reverse('annonce_creer'), self.annonce_data(action='soumettre'))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_vendeur_est_toujours_utilisateur_connecte(self):
        self.client.post(reverse('annonce_creer'), self.annonce_data(action='enregistrer'))
        annonce = Annonce.objects.get(vendeur=self.vendeur)
        self.assertEqual(annonce.vendeur, self.vendeur)
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_views -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_creer' not found`

- [ ] **Step 3: Écrire la vue**

Contenu complet de `vendor/core/src/annonces/views.py` :

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from .forms import AnnonceForm
from .models import Annonce, AnnoncePhoto


class _CompteActifRequisMixin(LoginRequiredMixin):
    login_url = 'connexion_vendeur'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.statut_compte != request.user.StatutCompte.ACTIF:
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
```

`_CompteActifRequisMixin` sera réutilisé par les tâches suivantes (liste, édition,
publication) — toutes les vues de gestion d'annonces exigent un compte `actif`.

- [ ] **Step 4: Écrire les URLs de l'app**

Contenu complet de `vendor/core/src/annonces/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
]
```

- [ ] **Step 5: Inclure les URLs de l'app dans le projet**

Dans `vendor/core/src/core/urls.py`, remplacer :

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

par :

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('annonces/', include('annonces.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

- [ ] **Step 6: Écrire le template du wizard**

Contenu complet de `vendor/core/src/templates/annonces/annonce_form.html` — adapté du
wizard déjà construit côté admin (`admin/core/src/templates/annonces/annonce_form.html`),
avec l'en-tête simple du projet vendor (pas de sidebar admin) et l'étape 4 réduite à la
description + publication (aucune sélection de vendeur, `vendeur = request.user`) :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Nouvelle annonce — Djona Vendeur{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","primary-container":"#1a5276","secondary":"#865300","secondary-container":"#fea520","surface":"#f8f9f9","surface-container":"#edeeee","surface-container-low":"#f3f4f4","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf","error":"#ba1a1a","error-container":"#ffdad6","on-error-container":"#93000a"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-background font-body-md text-on-surface min-h-screen flex flex-col">
    <header class="w-full border-b border-outline-variant/30 bg-surface">
        <div class="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <img alt="Djona" class="h-8 w-auto object-contain" src="{% static 'app/assets/img/djona-logo.png' %}">
                <span class="font-headline-md text-primary font-bold">Nouvelle annonce</span>
            </div>
            <a class="text-sm font-semibold text-primary hover:underline" href="{% url 'mes_annonces' %}">Annuler</a>
        </div>
    </header>

    <main class="flex-1 px-6 py-8">
        <div class="flex items-center justify-between max-w-3xl mx-auto py-2 gap-2">
            <span data-step-indicator="1" class="font-label-md text-label-md text-primary font-bold">① Infos</span>
            <span class="flex-1 h-px bg-outline-variant"></span>
            <span data-step-indicator="2" class="font-label-md text-label-md text-on-surface-variant">② Caractéristiques</span>
            <span class="flex-1 h-px bg-outline-variant"></span>
            <span data-step-indicator="3" class="font-label-md text-label-md text-on-surface-variant">③ Photos</span>
            <span class="flex-1 h-px bg-outline-variant"></span>
            <span data-step-indicator="4" class="font-label-md text-label-md text-on-surface-variant">④ Publication</span>
        </div>

        {% if form.non_field_errors %}
        <div class="max-w-3xl mx-auto mt-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container font-label-sm text-sm flex flex-col gap-1">
            {% for error in form.non_field_errors %}<p>{{ error }}</p>{% endfor %}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" class="max-w-3xl mx-auto mt-6 bg-surface-container-lowest rounded-2xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] p-6 md:p-8 flex flex-col gap-6">
            {% csrf_token %}

            <div data-step="1" class="flex flex-col gap-4">
                <h2 class="font-headline-md text-lg text-primary">Informations générales</h2>

                <div class="flex flex-col gap-1 {% if form.marque.errors %}field-error{% endif %}">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.marque.id_for_label }}">Marque</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.marque.id_for_label }}" name="marque" required type="text" value="{{ form.marque.value|default:'' }}">
                    {% if form.marque.errors %}<p class="text-[11px] text-error">{{ form.marque.errors.0 }}</p>{% endif %}
                </div>

                <div class="flex flex-col gap-1 {% if form.modele.errors %}field-error{% endif %}">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.modele.id_for_label }}">Modèle</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.modele.id_for_label }}" name="modele" required type="text" value="{{ form.modele.value|default:'' }}">
                    {% if form.modele.errors %}<p class="text-[11px] text-error">{{ form.modele.errors.0 }}</p>{% endif %}
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div class="flex flex-col gap-1 {% if form.annee.errors %}field-error{% endif %}">
                        <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.annee.id_for_label }}">Année</label>
                        <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.annee.id_for_label }}" min="1980" name="annee" required type="number" value="{{ form.annee.value|default:'' }}">
                        {% if form.annee.errors %}<p class="text-[11px] text-error">{{ form.annee.errors.0 }}</p>{% endif %}
                    </div>
                    <div class="flex flex-col gap-1 {% if form.prix.errors %}field-error{% endif %}">
                        <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.prix.id_for_label }}">Prix (CFA)</label>
                        <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.prix.id_for_label }}" min="0" name="prix" required type="number" value="{{ form.prix.value|default:'' }}">
                        {% if form.prix.errors %}<p class="text-[11px] text-error">{{ form.prix.errors.0 }}</p>{% endif %}
                    </div>
                </div>

                <div class="flex justify-end mt-2">
                    <button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
                </div>
            </div>

            <div data-step="2" class="hidden flex flex-col gap-4">
                <h2 class="font-headline-md text-lg text-primary">Caractéristiques</h2>

                <div class="flex flex-col gap-1 {% if form.kilometrage.errors %}field-error{% endif %}">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.kilometrage.id_for_label }}">Kilométrage</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.kilometrage.id_for_label }}" min="0" name="kilometrage" required type="number" value="{{ form.kilometrage.value|default:'' }}">
                    {% if form.kilometrage.errors %}<p class="text-[11px] text-error">{{ form.kilometrage.errors.0 }}</p>{% endif %}
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div class="flex flex-col gap-1 {% if form.carburant.errors %}field-error{% endif %}">
                        <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.carburant.id_for_label }}">Carburant</label>
                        <select class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.carburant.id_for_label }}" name="carburant" required>
                            {% for value, label in form.fields.carburant.choices %}<option value="{{ value }}" {% if form.carburant.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
                        </select>
                        {% if form.carburant.errors %}<p class="text-[11px] text-error">{{ form.carburant.errors.0 }}</p>{% endif %}
                    </div>
                    <div class="flex flex-col gap-1 {% if form.boite_vitesses.errors %}field-error{% endif %}">
                        <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.boite_vitesses.id_for_label }}">Boîte de vitesses</label>
                        <select class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.boite_vitesses.id_for_label }}" name="boite_vitesses" required>
                            {% for value, label in form.fields.boite_vitesses.choices %}<option value="{{ value }}" {% if form.boite_vitesses.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
                        </select>
                        {% if form.boite_vitesses.errors %}<p class="text-[11px] text-error">{{ form.boite_vitesses.errors.0 }}</p>{% endif %}
                    </div>
                </div>

                <div class="flex flex-col gap-1 {% if form.couleur.errors %}field-error{% endif %}">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.couleur.id_for_label }}">Couleur</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.couleur.id_for_label }}" name="couleur" required type="text" value="{{ form.couleur.value|default:'' }}">
                    {% if form.couleur.errors %}<p class="text-[11px] text-error">{{ form.couleur.errors.0 }}</p>{% endif %}
                </div>

                <div class="flex justify-between mt-2">
                    <button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-sm flex items-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
                    <button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
                </div>
            </div>

            <div data-step="3" class="hidden flex flex-col gap-4">
                <h2 class="font-headline-md text-lg text-primary">Photos</h2>
                <p class="text-sm text-on-surface-variant">Jusqu'à 8 photos. <span id="photo-count">0/8</span></p>

                <label class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-outline-variant rounded-lg py-8 cursor-pointer hover:border-primary transition-colors" for="id_photos">
                    <span class="material-symbols-outlined text-primary text-[32px]">add_photo_alternate</span>
                    <span class="font-label-md text-sm text-on-surface-variant">Ajouter des photos</span>
                </label>
                <input accept="image/*" class="hidden" id="id_photos" multiple name="photos" type="file">

                <div class="grid grid-cols-3 sm:grid-cols-4 gap-3" id="photo-grid"></div>

                <div class="flex justify-between mt-2">
                    <button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-sm flex items-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
                    <button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
                </div>
            </div>

            <div data-step="4" class="hidden flex flex-col gap-4">
                <h2 class="font-headline-md text-lg text-primary">Description & publication</h2>

                <div class="flex flex-col gap-1 {% if form.description.errors %}field-error{% endif %}">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.description.id_for_label }}">Description</label>
                    <textarea class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.description.id_for_label }}" name="description" required rows="4">{{ form.description.value|default:'' }}</textarea>
                    {% if form.description.errors %}<p class="text-[11px] text-error">{{ form.description.errors.0 }}</p>{% endif %}
                </div>

                <div class="flex flex-col sm:flex-row justify-between gap-3 mt-2">
                    <button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-sm flex items-center justify-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
                    <div class="flex flex-col sm:flex-row gap-3">
                        <button class="px-6 py-3 border-2 border-primary text-primary rounded-lg font-label-md text-sm" name="action" type="submit" value="enregistrer">Enregistrer comme brouillon</button>
                        <button class="px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm" name="action" type="submit" value="soumettre">Soumettre pour validation</button>
                    </div>
                </div>
            </div>

        </form>
    </main>
</div>
{% endblock %}

{% block scripts %}
<script>
(function () {
  var steps = Array.prototype.slice.call(document.querySelectorAll('[data-step]'));
  var indicators = Array.prototype.slice.call(document.querySelectorAll('[data-step-indicator]'));
  var submitButtons = Array.prototype.slice.call(document.querySelectorAll('button[type="submit"]'));
  var lastStep = steps.length;
  var currentStep = 1;

  function showStep(stepNumber) {
    steps.forEach(function (el) {
      el.classList.toggle('hidden', Number(el.dataset.step) !== stepNumber);
    });
    indicators.forEach(function (el) {
      var isActive = Number(el.dataset.stepIndicator) === stepNumber;
      el.classList.toggle('text-primary', isActive);
      el.classList.toggle('font-bold', isActive);
      el.classList.toggle('text-on-surface-variant', !isActive);
    });
    submitButtons.forEach(function (btn) {
      btn.disabled = stepNumber !== lastStep;
    });
    currentStep = stepNumber;
  }

  document.querySelectorAll('.wizard-next').forEach(function (button) {
    button.addEventListener('click', function () {
      var currentBlock = document.querySelector('[data-step="' + currentStep + '"]');
      var fields = currentBlock.querySelectorAll('input, select, textarea');
      for (var i = 0; i < fields.length; i++) {
        if (!fields[i].reportValidity()) return;
      }
      showStep(currentStep + 1);
    });
  });

  document.querySelectorAll('.wizard-prev').forEach(function (button) {
    button.addEventListener('click', function () {
      showStep(currentStep - 1);
    });
  });

  var firstErrorBlock = document.querySelector('.field-error');
  var initialStep = firstErrorBlock ? Number(firstErrorBlock.closest('[data-step]').dataset.step) : 1;
  showStep(initialStep);

  var photoInput = document.getElementById('id_photos');
  var photoGrid = document.getElementById('photo-grid');
  var photoCount = document.getElementById('photo-count');
  var photoFiles = [];

  function renderPhotoGrid() {
    photoGrid.innerHTML = '';
    photoFiles.forEach(function (file, index) {
      var url = URL.createObjectURL(file);
      var item = document.createElement('div');
      item.className = 'relative w-full aspect-square rounded-lg overflow-hidden bg-surface-container-low';
      item.innerHTML = '<img src="' + url + '" class="w-full h-full object-cover" alt="Photo ' + (index + 1) + '">' +
        '<button type="button" data-index="' + index + '" class="remove-photo absolute top-1 right-1 w-6 h-6 rounded-full bg-error text-white flex items-center justify-center">' +
        '<span class="material-symbols-outlined text-[16px]">close</span></button>';
      photoGrid.appendChild(item);
    });
    photoCount.textContent = photoFiles.length + '/8';
    var dataTransfer = new DataTransfer();
    photoFiles.forEach(function (file) { dataTransfer.items.add(file); });
    photoInput.files = dataTransfer.files;
  }

  photoInput.addEventListener('change', function () {
    var incoming = Array.prototype.slice.call(photoInput.files);
    var room = 8 - photoFiles.length;
    photoFiles = photoFiles.concat(incoming.slice(0, Math.max(room, 0)));
    renderPhotoGrid();
  });

  photoGrid.addEventListener('click', function (event) {
    var button = event.target.closest('.remove-photo');
    if (!button) return;
    photoFiles.splice(Number(button.dataset.index), 1);
    renderPhotoGrid();
  });
})();
</script>
{% endblock %}
```

(La logique JS `vendeur_mode`/`vendeur-existant-block` de la version admin est retirée
— il n'y a plus de sélection de vendeur.)

- [ ] **Step 7: Ajouter un lien temporaire vers le wizard**

Le lien « Mes annonces » du dashboard (`tableau_de_bord.html`, état `actif`) pointe
encore vers `href="#"` depuis le plan précédent. Il sera câblé vers la vraie liste dans
la Task 4 — laisser tel quel pour l'instant (ce step ne modifie rien, c'est un
rappel).

- [ ] **Step 8: Vérifier que les tests passent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_views -v 2`
Expected: PASS (5 tests) — `test_creation_sans_action_sauvegarde_en_brouillon` et
`test_creation_avec_action_soumettre_passe_en_attente` échoueront jusqu'à la Task 4
(`reverse('mes_annonces')` n'existe pas encore). C'est attendu à ce stade — la Task 4
les fait passer.

- [ ] **Step 9: Commit**

```bash
cd vendor/core
git add -A src/annonces/views.py src/annonces/urls.py src/annonces/tests/test_views.py src/templates/annonces/annonce_form.html src/core/urls.py
git commit -m "feat(annonces): ajoute le wizard de création d'annonce (vendor)"
```

---

## Task 4: Liste « Mes annonces » (vendor)

> **Note d'exécution :** cette tâche s'est révélée dépendre de la Task 6
> (« Publier ») plus tôt que prévu — `assertRedirects` (par défaut
> `fetch_redirect_response=True`) fait que le test de la Task 3
> `test_creation_sans_action_sauvegarde_en_brouillon` rend effectivement cette
> page de liste après création d'une annonce `brouillon`, ce qui déclenche
> `{% url 'annonce_publier' %}` avant que cette route existe. La Task 6 a donc
> été fusionnée dans cette tâche (implémentée et commitée ensemble) plutôt que
> reportée. La section Task 6 plus bas est conservée pour référence mais son
> contenu est déjà fait ici — ne pas la ré-exécuter séparément.

**Files:**
- Modify: `vendor/core/src/annonces/views.py`
- Modify: `vendor/core/src/annonces/urls.py`
- Create: `vendor/core/src/templates/annonces/mes_annonces.html`
- Modify: `vendor/core/src/templates/app/layout/tableau_de_bord.html`

- [ ] **Step 1: Vérifier que les deux tests en attente de la Task 3 échouent toujours pour la bonne raison**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_views -v 2`
Expected: `NoReverseMatch: Reverse for 'mes_annonces' not found` sur les deux tests
concernés.

- [ ] **Step 2: Ajouter la vue liste**

Dans `vendor/core/src/annonces/views.py`, ajouter en haut du fichier l'import
`ListView`, et la classe après `AnnonceCreateView` :

```python
from django.views.generic import ListView
```

(à ajouter à la ligne `from django.views import View` existante, qui devient :)

```python
from django.views import View
from django.views.generic import ListView
```

Puis, à la fin du fichier :

```python
class MesAnnoncesListView(_CompteActifRequisMixin, ListView):
    model = Annonce
    template_name = 'annonces/mes_annonces.html'
    context_object_name = 'annonces'

    def get_queryset(self):
        return Annonce.objects.filter(vendeur=self.request.user).order_by('-created_at')
```

- [ ] **Step 3: Ajouter la route**

Contenu complet de `vendor/core/src/annonces/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.MesAnnoncesListView.as_view(), name='mes_annonces'),
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
]
```

- [ ] **Step 4: Écrire le template de la liste**

Contenu complet de `vendor/core/src/templates/annonces/mes_annonces.html` :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Mes annonces — Djona Vendeur{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","secondary":"#865300","secondary-container":"#fea520","surface":"#f8f9f9","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-background font-body-md text-on-surface min-h-screen flex flex-col">
    <header class="w-full border-b border-outline-variant/30 bg-surface">
        <div class="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <img alt="Djona" class="h-8 w-auto object-contain" src="{% static 'app/assets/img/djona-logo.png' %}">
                <span class="font-headline-md text-primary font-bold">Mes annonces</span>
            </div>
            <a class="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-semibold hover:bg-primary/90 transition-colors" href="{% url 'annonce_creer' %}">
                + Nouvelle annonce
            </a>
        </div>
    </header>

    <main class="flex-1 max-w-4xl w-full mx-auto px-6 py-8">
        {% if messages %}
        <div class="mb-6 flex flex-col gap-2">
            {% for message in messages %}
            <div class="px-4 py-3 rounded-lg bg-green-100 text-green-800 text-sm font-medium">{{ message }}</div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="flex flex-col gap-3">
            {% for annonce in annonces %}
            <div class="bg-surface-container-lowest rounded-lg shadow-sm p-5 flex items-center justify-between gap-4">
                <div>
                    <p class="font-semibold text-on-surface">{{ annonce.marque }} {{ annonce.modele }} ({{ annonce.annee }})</p>
                    <p class="text-sm text-on-surface-variant">{{ annonce.prix }} CFA · {{ annonce.kilometrage }} km</p>
                </div>
                <div class="flex items-center gap-3">
                    {% if annonce.statut == 'brouillon' %}
                    <span class="px-3 py-1 rounded-full bg-surface-container text-on-surface-variant text-xs font-bold">Brouillon</span>
                    <form action="{% url 'annonce_publier' annonce.pk %}" method="post">
                        {% csrf_token %}
                        <button class="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-bold hover:bg-primary/90 transition-colors" type="submit">Publier</button>
                    </form>
                    {% elif annonce.statut == 'en_attente' %}
                    <span class="px-3 py-1 rounded-full bg-secondary-container/30 text-secondary text-xs font-bold">En attente de validation</span>
                    {% elif annonce.statut == 'publiee' %}
                    <span class="px-3 py-1 rounded-full bg-green-100 text-green-700 text-xs font-bold">Publiée</span>
                    {% else %}
                    <span class="px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-bold">Refusée</span>
                    <a class="px-3 py-1.5 rounded-lg border border-primary text-primary text-xs font-bold hover:bg-primary/5 transition-colors" href="{% url 'annonce_modifier' annonce.pk %}">Corriger</a>
                    {% endif %}
                </div>
            </div>
            {% empty %}
            <div class="text-center py-16 text-on-surface-variant">
                <p>Vous n'avez pas encore d'annonce.</p>
                <a class="text-primary font-semibold hover:underline" href="{% url 'annonce_creer' %}">Créer votre première annonce</a>
            </div>
            {% endfor %}
        </div>
    </main>
</div>
{% endblock %}
```

(Les liens `annonce_publier` et `annonce_modifier` sont ajoutés aux Tasks 5 et 6 —
`{% url %}` échouera tant qu'ils n'existent pas si une annonce `brouillon` ou
`refusee` est présente. Aucune annonce de test n'a ce statut avant la Task 6, donc ceci
ne bloque pas la Task 4.)

- [ ] **Step 5: Câbler le lien « Mes annonces » du dashboard**

Dans `vendor/core/src/templates/app/layout/tableau_de_bord.html`, la branche `{% else
%}` (statut `actif`) contient :

```html
            <a class="mt-2 px-6 py-3 bg-primary text-on-primary rounded-lg font-semibold hover:bg-primary/90 transition-colors" href="#">
                Mes annonces
            </a>
```

Remplacer par :

```html
            <a class="mt-2 px-6 py-3 bg-primary text-on-primary rounded-lg font-semibold hover:bg-primary/90 transition-colors" href="{% url 'mes_annonces' %}">
                Mes annonces
            </a>
```

- [ ] **Step 6: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test annonces -v 2`
Expected: PASS (14 tests : 4 modèles + 5 formulaire + 5 vues)

- [ ] **Step 7: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (36 tests).

- [ ] **Step 8: Commit**

```bash
cd vendor/core
git add -A src/annonces/views.py src/annonces/urls.py src/templates/annonces/mes_annonces.html src/templates/app/layout/tableau_de_bord.html
git commit -m "feat(annonces): ajoute la liste Mes annonces (vendor)"
```

---

## Task 5: Édition d'une annonce (vendor)

**Files:**
- Modify: `vendor/core/src/annonces/views.py`
- Modify: `vendor/core/src/annonces/urls.py`
- Create: `vendor/core/src/templates/annonces/annonce_form_edition.html`
- Modify: `vendor/core/src/annonces/tests/test_views.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `vendor/core/src/annonces/tests/test_views.py` :

```python
class AnnonceUpdateViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def create_annonce(self, vendeur=None, statut=Annonce.Statut.BROUILLON):
        return Annonce.objects.create(
            vendeur=vendeur or self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris',
            description='Très bon état.', statut=statut,
        )

    def test_brouillon_est_modifiable(self):
        annonce = self.create_annonce()
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 200)

    def test_edition_annonce_refusee_repasse_en_brouillon(self):
        annonce = self.create_annonce(statut=Annonce.Statut.REFUSEE)
        response = self.client.post(reverse('annonce_modifier', args=[annonce.pk]), {
            'marque': 'Toyota', 'modele': 'Corolla', 'annee': 2019, 'prix': 9000000,
            'kilometrage': 45000, 'carburant': Annonce.Carburant.ESSENCE,
            'boite_vitesses': Annonce.BoiteVitesses.AUTOMATIQUE, 'couleur': 'Gris',
            'description': 'Très bon état, prix ajusté.',
        })
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertEqual(annonce.prix, 9000000)

    def test_en_attente_non_modifiable(self):
        annonce = self.create_annonce(statut=Annonce.Statut.EN_ATTENTE)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))

    def test_publiee_non_modifiable(self):
        annonce = self.create_annonce(statut=Annonce.Statut.PUBLIEE)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))

    def test_annonce_dun_autre_vendeur_renvoie_404(self):
        annonce = self.create_annonce(vendeur=self.autre_vendeur)
        response = self.client.get(reverse('annonce_modifier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 404)
```

Ajouter `from django.test import TestCase` et les autres imports déjà présents en haut
du fichier restent inchangés (`Annonce`, `Utilisateur`, `reverse` déjà importés par la
classe `AnnonceCreateViewTest`).

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_views.AnnonceUpdateViewTest -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_modifier' not found`

- [ ] **Step 3: Ajouter la vue d'édition**

Dans `vendor/core/src/annonces/views.py`, la ligne d'import existante :

```python
from django.shortcuts import redirect, render
```

devient :

```python
from django.shortcuts import get_object_or_404, redirect, render
```

Puis ajouter à la fin du fichier :

```python
class AnnonceUpdateView(_CompteActifRequisMixin, View):
    template_name = 'annonces/annonce_form_edition.html'
    statuts_modifiables = (Annonce.Statut.BROUILLON, Annonce.Statut.REFUSEE)

    def get_annonce(self, request, pk):
        return get_object_or_404(Annonce, pk=pk, vendeur=request.user)

    def get(self, request, pk):
        annonce = self.get_annonce(request, pk)
        if annonce.statut not in self.statuts_modifiables:
            messages.info(request, "Cette annonce ne peut plus être modifiée pour le moment.")
            return redirect('mes_annonces')
        return render(request, self.template_name, {'form': AnnonceForm(instance=annonce), 'annonce': annonce})

    def post(self, request, pk):
        annonce = self.get_annonce(request, pk)
        if annonce.statut not in self.statuts_modifiables:
            messages.info(request, "Cette annonce ne peut plus être modifiée pour le moment.")
            return redirect('mes_annonces')

        form = AnnonceForm(request.POST, request.FILES, instance=annonce)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'annonce': annonce})

        with transaction.atomic():
            annonce = form.save(commit=False)
            annonce.statut = Annonce.Statut.BROUILLON
            annonce.save()
            for index, photo in enumerate(request.FILES.getlist('photos')):
                AnnoncePhoto.objects.create(annonce=annonce, image=photo, ordre=index)

        messages.success(request, 'Annonce mise à jour.')
        return redirect('mes_annonces')
```

`get_object_or_404(Annonce, pk=pk, vendeur=request.user)` : le queryset est scopé au
vendeur connecté dès la recherche — l'annonce d'un autre vendeur renvoie 404, jamais un
403 qui révélerait son existence.

- [ ] **Step 4: Ajouter la route**

Contenu complet de `vendor/core/src/annonces/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.MesAnnoncesListView.as_view(), name='mes_annonces'),
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
    path('<int:pk>/modifier/', views.AnnonceUpdateView.as_view(), name='annonce_modifier'),
]
```

- [ ] **Step 5: Écrire le template d'édition**

`vendor/core/src/templates/annonces/annonce_form_edition.html` réutilise la même
structure de formulaire que `annonce_form.html`, mais en une seule page (pas de wizard
— l'utilisateur corrige simplement les champs déjà remplis) :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Modifier l'annonce — Djona Vendeur{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","surface":"#f8f9f9","surface-container-low":"#f3f4f4","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf","error":"#ba1a1a","error-container":"#ffdad6","on-error-container":"#93000a"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-background font-body-md text-on-surface min-h-screen flex flex-col">
    <header class="w-full border-b border-outline-variant/30 bg-surface">
        <div class="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <img alt="Djona" class="h-8 w-auto object-contain" src="{% static 'app/assets/img/djona-logo.png' %}">
                <span class="font-headline-md text-primary font-bold">Modifier l'annonce</span>
            </div>
            <a class="text-sm font-semibold text-primary hover:underline" href="{% url 'mes_annonces' %}">Annuler</a>
        </div>
    </header>

    <main class="flex-1 px-6 py-8">
        {% if form.non_field_errors %}
        <div class="max-w-3xl mx-auto mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm flex flex-col gap-1">
            {% for error in form.non_field_errors %}<p>{{ error }}</p>{% endfor %}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" class="max-w-3xl mx-auto bg-surface-container-lowest rounded-2xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] p-6 md:p-8 flex flex-col gap-4">
            {% csrf_token %}

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.marque.id_for_label }}">Marque</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.marque.id_for_label }}" name="marque" required type="text" value="{{ form.marque.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.modele.id_for_label }}">Modèle</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.modele.id_for_label }}" name="modele" required type="text" value="{{ form.modele.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.annee.id_for_label }}">Année</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.annee.id_for_label }}" min="1980" name="annee" required type="number" value="{{ form.annee.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.prix.id_for_label }}">Prix (CFA)</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.prix.id_for_label }}" min="0" name="prix" required type="number" value="{{ form.prix.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.kilometrage.id_for_label }}">Kilométrage</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.kilometrage.id_for_label }}" min="0" name="kilometrage" required type="number" value="{{ form.kilometrage.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.couleur.id_for_label }}">Couleur</label>
                    <input class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.couleur.id_for_label }}" name="couleur" required type="text" value="{{ form.couleur.value|default:'' }}">
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.carburant.id_for_label }}">Carburant</label>
                    <select class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.carburant.id_for_label }}" name="carburant" required>
                        {% for value, label in form.fields.carburant.choices %}<option value="{{ value }}" {% if form.carburant.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
                    </select>
                </div>
                <div class="flex flex-col gap-1">
                    <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.boite_vitesses.id_for_label }}">Boîte de vitesses</label>
                    <select class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.boite_vitesses.id_for_label }}" name="boite_vitesses" required>
                        {% for value, label in form.fields.boite_vitesses.choices %}<option value="{{ value }}" {% if form.boite_vitesses.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
                    </select>
                </div>
            </div>

            <div class="flex flex-col gap-1">
                <label class="font-label-md text-sm text-on-surface-variant" for="{{ form.description.id_for_label }}">Description</label>
                <textarea class="w-full px-4 py-3 bg-surface-container-low rounded-lg text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.description.id_for_label }}" name="description" required rows="4">{{ form.description.value|default:'' }}</textarea>
            </div>

            <button class="self-end px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm" type="submit">Enregistrer les modifications</button>
        </form>
    </main>
</div>
{% endblock %}
```

- [ ] **Step 6: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test annonces.tests.test_views -v 2`
Expected: PASS (10 tests)

- [ ] **Step 7: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (41 tests).

- [ ] **Step 8: Commit**

```bash
cd vendor/core
git add -A src/annonces/views.py src/annonces/urls.py src/annonces/tests/test_views.py src/templates/annonces/annonce_form_edition.html
git commit -m "feat(annonces): ajoute l'édition d'une annonce (brouillon/refusée)"
```

---

## Task 6: Action « Publier » (vendor) — DÉJÀ FAIT, voir Task 4

> Cette tâche a été fusionnée dans la Task 4 (voir la note d'exécution en haut de
> cette dernière) — ne pas ré-exécuter le contenu ci-dessous séparément, il est
> conservé uniquement pour référence/traçabilité.

**Files:**
- Modify: `vendor/core/src/annonces/views.py`
- Modify: `vendor/core/src/annonces/urls.py`
- Modify: `vendor/core/src/annonces/tests/test_views.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `vendor/core/src/annonces/tests/test_views.py` :

```python
class AnnoncePublierViewTest(TestCase):
    def setUp(self):
        self.vendeur = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.autre_vendeur = Utilisateur.objects.create_user(
            email='autre@exemple.ci', password='MotDePasse1', nom='Diallo', prenom='Fatou',
            telephone='0102030406', statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        self.client.force_login(self.vendeur)

    def create_annonce(self, vendeur=None, statut=Annonce.Statut.BROUILLON):
        return Annonce.objects.create(
            vendeur=vendeur or self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Gris',
            description='Très bon état.', statut=statut,
        )

    def test_publier_un_brouillon_passe_en_attente(self):
        annonce = self.create_annonce()
        response = self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        self.assertRedirects(response, reverse('mes_annonces'))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_publier_une_annonce_deja_en_attente_ne_fait_rien(self):
        annonce = self.create_annonce(statut=Annonce.Statut.EN_ATTENTE)
        self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        annonce.refresh_from_db()
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_publier_refuse_get(self):
        annonce = self.create_annonce()
        response = self.client.get(reverse('annonce_publier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 405)

    def test_annonce_dun_autre_vendeur_renvoie_404(self):
        annonce = self.create_annonce(vendeur=self.autre_vendeur)
        response = self.client.post(reverse('annonce_publier', args=[annonce.pk]))
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test annonces.tests.test_views.AnnoncePublierViewTest -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_publier' not found`

- [ ] **Step 3: Ajouter la vue d'action**

Dans `vendor/core/src/annonces/views.py`, ajouter à la fin du fichier :

```python
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator


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
```

- [ ] **Step 4: Ajouter la route**

Contenu complet de `vendor/core/src/annonces/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.MesAnnoncesListView.as_view(), name='mes_annonces'),
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
    path('<int:pk>/modifier/', views.AnnonceUpdateView.as_view(), name='annonce_modifier'),
    path('<int:pk>/publier/', views.AnnoncePublierView.as_view(), name='annonce_publier'),
]
```

- [ ] **Step 5: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test annonces.tests.test_views -v 2`
Expected: PASS (14 tests)

- [ ] **Step 6: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (45 tests).

- [ ] **Step 7: Commit**

```bash
cd vendor/core
git add -A src/annonces/views.py src/annonces/urls.py src/annonces/tests/test_views.py
git commit -m "feat(annonces): ajoute l'action publier (brouillon -> en_attente)"
```

---

## Task 7: Modèles miroirs `AnnonceMirror` / `AnnoncePhotoMirror` (admin)

**Files:**
- Modify: `admin/core/src/moderation/models.py`
- Create: `admin/core/src/moderation/tests/test_models_annonce.py`

- [ ] **Step 1: Écrire le test qui échoue**

Contenu complet de `admin/core/src/moderation/tests/test_models_annonce.py` :

```python
from django.test import TestCase

from moderation.models import AnnonceMirror, AnnoncePhotoMirror, CompteVendeur


class AnnonceMirrorTest(TestCase):
    databases = {'vendor_db'}

    def setUp(self):
        self.vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='mirror-vendeur@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )

    def tearDown(self):
        CompteVendeur.objects.using('vendor_db').filter(email='mirror-vendeur@exemple.ci').delete()

    def test_lit_les_annonces_reelles(self):
        annonce = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Toyota', modele='Corolla', annee=2019,
            prix=8500000, kilometrage=45000, carburant='essence', boite_vitesses='automatique',
            couleur='Gris', description='Très bon état.', statut=AnnonceMirror.Statut.EN_ATTENTE,
            created_at='2026-08-27T10:00:00Z',
        )
        AnnoncePhotoMirror.objects.using('vendor_db').create(annonce=annonce, image='annonces/test.jpg', ordre=0)

        relue = AnnonceMirror.objects.using('vendor_db').get(pk=annonce.pk)
        self.assertEqual(relue.marque, 'Toyota')
        self.assertEqual(relue.photos.count(), 1)
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation.tests.test_models_annonce -v 2`
Expected: `ImportError: cannot import name 'AnnonceMirror' from 'moderation.models'`

- [ ] **Step 3: Ajouter les modèles miroirs**

Ajouter à la fin de `admin/core/src/moderation/models.py` (le contenu existant —
`CompteVendeur` — ne change pas) :

```python
class AnnonceMirror(models.Model):
    """Miroir en lecture/écriture de vendor.annonces.Annonce (schéma djona_vendor,
    connexion 'vendor_db'). Jamais migré depuis ce projet."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_ATTENTE = 'en_attente', 'En attente'
        PUBLIEE = 'publiee', 'Publiée'
        REFUSEE = 'refusee', 'Refusée'

    vendeur = models.ForeignKey(
        CompteVendeur, on_delete=models.DO_NOTHING, related_name='annonces', db_constraint=False,
    )
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20)
    boite_vitesses = models.CharField(max_length=20)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'


class AnnoncePhotoMirror(models.Model):
    annonce = models.ForeignKey(
        AnnonceMirror, on_delete=models.DO_NOTHING, related_name='photos', db_constraint=False,
    )
    image = models.ImageField(upload_to='annonces/%Y/%m/')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'annonce_photos'
        ordering = ['ordre']
```

- [ ] **Step 4: Vérifier que le test passe**

Run: `../venv/Scripts/python.exe manage.py test moderation.tests.test_models_annonce -v 2`
Expected: PASS

- [ ] **Step 5: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (36 tests : 35 existants + 1 nouveau).

- [ ] **Step 6: Commit**

```bash
cd admin/core
git add -A src/moderation/models.py src/moderation/tests/test_models_annonce.py
git commit -m "feat(moderation): ajoute les modèles miroirs AnnonceMirror/AnnoncePhotoMirror"
```

---

## Task 8: File de validation des annonces (admin) — liste et détail

**Files:**
- Modify: `admin/core/src/moderation/views.py`
- Modify: `admin/core/src/moderation/urls.py`
- Create: `admin/core/src/templates/moderation/annonce_liste.html`
- Create: `admin/core/src/templates/moderation/annonce_detail.html`
- Create: `admin/core/src/moderation/tests/test_views_annonce.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Contenu complet de `admin/core/src/moderation/tests/test_views_annonce.py` :

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import AnnonceMirror, CompteVendeur

User = get_user_model()


class AnnonceModerationListViewTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='motdepasse', is_staff=True)
        self.vendeur = CompteVendeur.objects.using('vendor_db').create(
            email='mod-vendeur@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        self.annonce_en_attente = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Toyota', modele='Corolla', annee=2019, prix=8500000,
            kilometrage=45000, carburant='essence', boite_vitesses='automatique', couleur='Gris',
            description='Très bon état.', statut=AnnonceMirror.Statut.EN_ATTENTE,
            created_at='2026-08-27T10:00:00Z',
        )
        self.annonce_brouillon = AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur, marque='Honda', modele='Civic', annee=2020, prix=9500000,
            kilometrage=30000, carburant='essence', boite_vitesses='manuelle', couleur='Noir',
            description='Comme neuve.', statut=AnnonceMirror.Statut.BROUILLON,
            created_at='2026-08-27T09:00:00Z',
        )

    def tearDown(self):
        AnnonceMirror.objects.using('vendor_db').filter(vendeur=self.vendeur).delete()
        CompteVendeur.objects.using('vendor_db').filter(pk=self.vendeur.pk).delete()

    def test_requiert_authentification_staff(self):
        response = self.client.get(reverse('annonce_moderation_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('annonce_moderation_liste')}")

    def test_liste_seulement_les_annonces_en_attente(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_moderation_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Corolla')
        self.assertNotContains(response, 'Civic')

    def test_detail_affiche_les_infos_completes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_moderation_detail', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota')
        self.assertContains(response, 'Ange')
        self.assertContains(response, '8500000')
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation.tests.test_views_annonce -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_moderation_liste' not found`

- [ ] **Step 3: Ajouter les vues**

Ajouter à la fin de `admin/core/src/moderation/views.py` :

```python
from .models import AnnonceMirror


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
```

Ajouter les imports manquants en haut du fichier (`ListView` déjà importé pour
`VendeurListView` ; ajouter `get_object_or_404` et `render`) :

```python
from django.shortcuts import get_object_or_404, redirect, render
```

(remplace la ligne `from django.shortcuts import get_object_or_404, redirect` déjà
présente depuis Task 6 du plan précédent).

- [ ] **Step 4: Ajouter les routes**

Contenu complet de `admin/core/src/moderation/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('vendeurs/', views.VendeurListView.as_view(), name='vendeur_liste'),
    path('vendeurs/<int:pk>/activer/', views.VendeurActiverView.as_view(), name='vendeur_activer'),
    path('vendeurs/<int:pk>/suspendre/', views.VendeurSuspendreView.as_view(), name='vendeur_suspendre'),
    path('annonces-a-valider/', views.AnnonceModerationListView.as_view(), name='annonce_moderation_liste'),
    path('annonces-a-valider/<int:pk>/', views.AnnonceModerationDetailView.as_view(), name='annonce_moderation_detail'),
]
```

- [ ] **Step 5: Écrire le template de la liste**

Contenu complet de `admin/core/src/templates/moderation/annonce_liste.html` :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Annonces à valider — Portail Admin{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","secondary":"#865300","secondary-container":"#fea520","surface":"#f8f9f9","surface-container":"#edeeee","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface min-h-screen lg:pl-72">
    <div class="max-w-6xl mx-auto px-container-margin-mobile lg:px-container-margin-desktop py-12">
        <h1 class="font-headline-md text-2xl text-primary mb-1">Annonces à valider</h1>
        <p class="text-on-surface-variant mb-8">Annonces soumises par les vendeurs, en attente de décision.</p>

        <div class="flex flex-col gap-3">
            {% for annonce in annonces %}
            <a class="bg-surface-container-lowest rounded-lg shadow-sm p-5 flex items-center justify-between gap-4 hover:shadow-md transition-shadow" href="{% url 'annonce_moderation_detail' annonce.pk %}">
                <div>
                    <p class="font-semibold text-on-surface">{{ annonce.marque }} {{ annonce.modele }} ({{ annonce.annee }})</p>
                    <p class="text-sm text-on-surface-variant">{{ annonce.vendeur.prenom }} {{ annonce.vendeur.nom }} · {{ annonce.prix }} CFA</p>
                </div>
                <span class="px-3 py-1 rounded-full bg-secondary-container/30 text-secondary text-xs font-bold">En attente</span>
            </a>
            {% empty %}
            <div class="text-center py-16 text-on-surface-variant">Aucune annonce en attente de validation.</div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Écrire le template de détail**

Contenu complet de `admin/core/src/templates/moderation/annonce_detail.html` :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}{{ annonce.marque }} {{ annonce.modele }} — Portail Admin{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","secondary":"#865300","surface":"#f8f9f9","surface-container":"#edeeee","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface min-h-screen lg:pl-72">
    <div class="max-w-3xl mx-auto px-container-margin-mobile lg:px-container-margin-desktop py-12">
        <a class="text-sm font-semibold text-primary hover:underline" href="{% url 'annonce_moderation_liste' %}">&larr; Retour à la liste</a>

        <div class="bg-surface-container-lowest rounded-2xl shadow-sm p-6 md:p-8 mt-4">
            <h1 class="font-headline-md text-2xl text-primary mb-1">{{ annonce.marque }} {{ annonce.modele }} ({{ annonce.annee }})</h1>
            <p class="text-on-surface-variant mb-6">Proposée par {{ annonce.vendeur.prenom }} {{ annonce.vendeur.nom }} — {{ annonce.vendeur.email }} — {{ annonce.vendeur.telephone }}</p>

            {% if photos %}
            <div class="grid grid-cols-3 sm:grid-cols-4 gap-3 mb-6">
                {% for photo in photos %}
                <img alt="Photo {{ forloop.counter }}" class="w-full aspect-square object-cover rounded-lg" src="{{ photo.image.url }}">
                {% endfor %}
            </div>
            {% endif %}

            <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6 text-sm">
                <div><p class="text-on-surface-variant">Prix</p><p class="font-semibold">{{ annonce.prix }} CFA</p></div>
                <div><p class="text-on-surface-variant">Kilométrage</p><p class="font-semibold">{{ annonce.kilometrage }} km</p></div>
                <div><p class="text-on-surface-variant">Carburant</p><p class="font-semibold">{{ annonce.get_carburant_display }}</p></div>
                <div><p class="text-on-surface-variant">Boîte</p><p class="font-semibold">{{ annonce.get_boite_vitesses_display }}</p></div>
                <div><p class="text-on-surface-variant">Couleur</p><p class="font-semibold">{{ annonce.couleur }}</p></div>
            </div>

            <p class="text-on-surface-variant mb-8">{{ annonce.description }}</p>

            <div class="flex flex-col sm:flex-row gap-3">
                <form action="{% url 'annonce_valider' annonce.pk %}" method="post">
                    {% csrf_token %}
                    <button class="w-full sm:w-auto px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-sm" type="submit">Publier</button>
                </form>
                <form action="{% url 'annonce_refuser' annonce.pk %}" method="post">
                    {% csrf_token %}
                    <button class="w-full sm:w-auto px-6 py-3 border-2 border-red-500 text-red-600 rounded-lg font-label-md text-sm" type="submit">Refuser</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

(`get_carburant_display`/`get_boite_vitesses_display` fonctionnent normalement sur
`AnnonceMirror` — `managed=False` n'affecte pas les méthodes générées par
`choices=`, seulement les migrations. Les liens `annonce_valider`/`annonce_refuser`
sont ajoutés à la Task 9.)

- [ ] **Step 7: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test moderation.tests.test_views_annonce -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_valider' not found` — normal, le template
de détail référence ces URLs avant qu'elles existent. Ce n'est pas bloquant pour CE
test (`test_detail_affiche_les_infos_completes` échouera avec cette erreur de rendu de
template). Passer directement à la Task 9 qui les ajoute.

- [ ] **Step 8: Commit**

```bash
cd admin/core
git add -A src/moderation src/templates/moderation
git commit -m "feat(moderation): ajoute la liste et le détail des annonces à valider"
```

---

## Task 9: Actions Publier / Refuser une annonce (admin)

**Files:**
- Modify: `admin/core/src/moderation/views.py`
- Modify: `admin/core/src/moderation/urls.py`
- Modify: `admin/core/src/moderation/tests/test_views_annonce.py`
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `admin/core/src/moderation/tests/test_views_annonce.py` :

```python
    def test_valider_publie_lannonce(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_valider', args=[self.annonce_en_attente.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_en_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_en_attente.statut, AnnonceMirror.Statut.PUBLIEE)

    def test_refuser_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('annonce_refuser', args=[self.annonce_en_attente.pk]))
        self.assertRedirects(response, reverse('annonce_moderation_liste'))
        self.annonce_en_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.annonce_en_attente.statut, AnnonceMirror.Statut.REFUSEE)

    def test_valider_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('annonce_valider', args=[self.annonce_en_attente.pk]))
        self.assertEqual(response.status_code, 405)
```

(Ces méthodes s'ajoutent à la classe `AnnonceModerationListViewTest` existante — même
indentation, mêmes `setUp`/`tearDown`.)

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation.tests.test_views_annonce -v 2`
Expected: `NoReverseMatch: Reverse for 'annonce_valider' not found` (toute la classe,
y compris `test_detail_affiche_les_infos_completes` resté en échec depuis la Task 8).

- [ ] **Step 3: Ajouter les vues d'action**

Ajouter à la fin de `admin/core/src/moderation/views.py` :

```python
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
        annonce.statut = self.nouveau_statut
        annonce.save(using='vendor_db', update_fields=['statut'])
        return redirect('annonce_moderation_liste')


class AnnonceValiderView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.PUBLIEE


class AnnonceRefuserView(_AnnonceActionView):
    nouveau_statut = AnnonceMirror.Statut.REFUSEE
```

- [ ] **Step 4: Ajouter les routes**

Contenu complet de `admin/core/src/moderation/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('vendeurs/', views.VendeurListView.as_view(), name='vendeur_liste'),
    path('vendeurs/<int:pk>/activer/', views.VendeurActiverView.as_view(), name='vendeur_activer'),
    path('vendeurs/<int:pk>/suspendre/', views.VendeurSuspendreView.as_view(), name='vendeur_suspendre'),
    path('annonces-a-valider/', views.AnnonceModerationListView.as_view(), name='annonce_moderation_liste'),
    path('annonces-a-valider/<int:pk>/', views.AnnonceModerationDetailView.as_view(), name='annonce_moderation_detail'),
    path('annonces-a-valider/<int:pk>/valider/', views.AnnonceValiderView.as_view(), name='annonce_valider'),
    path('annonces-a-valider/<int:pk>/refuser/', views.AnnonceRefuserView.as_view(), name='annonce_refuser'),
]
```

- [ ] **Step 5: Câbler le lien « Validation Queue » du dashboard**

Comme pour « Users » → « Vendeurs » dans le plan précédent, le dashboard admin a déjà
un lien « Validation Queue » (desktop et mobile) pointant vers `href="#"`. Dans
`admin/core/src/templates/app/layout/dashboard_admin.html`, la sidebar desktop
contient :

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Validation Queue</span>
</a>
```

Remplacer par :

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Annonces à valider</span>
</a>
```

Et la nav mobile basse :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="#">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
```

par :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
```

(Le libellé mobile reste « Validation » — espace réduit, déjà cohérent avec « Annonces
à valider » du desktop.)

- [ ] **Step 6: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test moderation -v 2`
Expected: PASS (13 tests : 1 modèle CompteVendeur + 1 modèle AnnonceMirror + 5 vues
vendeur + 6 vues annonce)

- [ ] **Step 7: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (48 tests).

- [ ] **Step 8: Commit**

```bash
cd admin/core
git add -A src/moderation src/templates/app/layout/dashboard_admin.html
git commit -m "feat(moderation): ajoute les actions valider/refuser une annonce"
```

---

## Task 10: Retrait de l'ancienne app `annonces` (admin)

**Files:**
- Delete: `admin/core/src/annonces/` (dossier complet)
- Delete: `admin/core/src/templates/annonces/` (dossier complet)
- Modify: `admin/core/src/core/settings.py` (`LOCAL_APPS`)
- Modify: `admin/core/src/core/urls.py`
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

L'ancien modèle `Vendeur` (sans authentification) et le wizard admin
(`AnnonceCreateView` créant une annonce pour un tiers) ne sont plus utilisés — le
vendeur crée maintenant ses propres annonces (Tasks 1-6). Ce retrait supprime aussi les
anciennes tables `vendeurs`/`annonces`/`annonce_photos` du schéma `djona_admin` (elles
ne contiennent que des données de test locales, aucune donnée réelle n'existe encore
sur ce projet).

- [ ] **Step 1: Retirer l'app des settings**

Dans `admin/core/src/core/settings.py`, `LOCAL_APPS` est actuellement :

```python
LOCAL_APPS = [
    'app',
    'annonces',
    'moderation',
]
```

Remplacer par :

```python
LOCAL_APPS = [
    'app',
    'moderation',
]
```

- [ ] **Step 2: Retirer les routes**

Dans `admin/core/src/core/urls.py`, remplacer :

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('annonces/', include('annonces.urls')),
    path('', include('moderation.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

par :

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('', include('moderation.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

- [ ] **Step 3: Retirer le lien « Nouvelle annonce » du dashboard**

Dans `admin/core/src/templates/app/layout/dashboard_admin.html`, la sidebar desktop
contient (premier lien du menu) :

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_creer' %}">
<span class="material-symbols-outlined mr-4">add_circle</span><span class="font-label-md text-label-md">Nouvelle annonce</span>
</a>
```

Supprimer entièrement ce bloc (les 3 lignes, y compris les balises `<a>`/`</a>`).

De même, dans la nav mobile basse :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_creer' %}">
<span class="material-symbols-outlined">add_circle</span><span class="font-label-sm text-label-sm">Annonce</span>
</a>
```

Supprimer entièrement ce bloc.

- [ ] **Step 4: Supprimer les fichiers de l'ancienne app**

Run:
```bash
cd admin/core/src
rm -rf annonces
rm -rf templates/annonces
```

- [ ] **Step 5: Vérifier que le projet démarre toujours**

Run:
```bash
../venv/Scripts/python.exe manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Régénérer la base de données locale (les anciennes tables ne sont plus gérées)**

L'app `annonces` n'existant plus, ses migrations (`0001_initial`, `0002_annonce`,
`0003_annoncephoto`) ont disparu avec elle. Django ne saura plus reconstruire le schéma
`djona_admin` depuis zéro si on le lui demandait — mais comme la base existe déjà
localement, `migrate` n'a rien à faire de plus, `django_migrations` gardant la trace de
ce qui a été appliqué. Aucune action nécessaire pour du développement local ; en
production, une vraie migration de suppression serait générée à la place — hors scope
ici (aucun déploiement en production n'existe encore pour ce projet).

Vérifier que les tables orphelines ne posent pas de problème :

```bash
../venv/Scripts/python.exe manage.py migrate
```
Expected: `No migrations to apply.`

- [ ] **Step 7: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (35 tests : 48 moins les 13 tests de l'ancienne app
`annonces.tests.*`, qui ont été supprimés avec le dossier).

- [ ] **Step 8: Vérification manuelle bout en bout complète**

Démarrer les deux serveurs :
```bash
cd vendor/core/src && ../venv/Scripts/python.exe manage.py runserver 8010
cd admin/core/src && ../venv/Scripts/python.exe manage.py runserver 8020
```

1. Vendor (`http://127.0.0.1:8010/`) : s'inscrire, se connecter → dashboard « en
   attente ».
2. Admin (`http://127.0.0.1:8020/`) : se connecter, aller sur « Vendeurs », activer le
   compte créé à l'étape 1.
3. Vendor : rafraîchir le dashboard → « Mes annonces » visible. Cliquer dessus, créer
   une annonce, cliquer « Soumettre pour validation ».
4. Admin : aller sur « Annonces à valider » (ex-« Validation Queue ») → l'annonce
   apparaît. Cliquer dessus, vérifier les infos, cliquer « Publier ».
5. Vendor : retourner sur « Mes annonces » → l'annonce affiche le badge « Publiée ».
6. Répéter les étapes 3-4 avec une deuxième annonce, mais cliquer « Refuser » à
   l'étape 4 côté admin.
7. Vendor : l'annonce refusée affiche « Refusée » avec un lien « Corriger » ; cliquer
   dessus, modifier un champ, enregistrer → l'annonce repasse en « Brouillon ».

Arrêter les deux serveurs une fois la vérification faite.

- [ ] **Step 9: Commit**

```bash
cd admin/core
git add -A src/core/settings.py src/core/urls.py src/templates/app/layout/dashboard_admin.html
git add -A -u src/annonces src/templates/annonces
git commit -m "refactor(admin): retire l'ancienne app annonces (remplacée par le flux vendeur + moderation)"
```

---

## Récapitulatif

À la fin de ce plan, le workflow complet des 4 points de la demande initiale est
fonctionnel :
1. Un vendeur s'inscrit et se connecte en choisissant son type (déjà en place avant ce
   plan).
2. Le dashboard admin liste les vendeurs et permet de les activer (plan précédent).
3. Un vendeur activé crée, édite et publie ses propres annonces.
4. L'admin valide (ou refuse) les annonces soumises, depuis une file de modération
   dédiée.

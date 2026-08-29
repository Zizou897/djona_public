# Publication d'une annonce véhicule (côté admin) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre au staff Djona de créer une fiche véhicule (« annonce ») depuis le portail admin, via un wizard visuel en 4 étapes, avec un statut brouillon/en attente/publiée/refusée.

**Architecture:** Nouvelle app Django `annonces` (modèles `Vendeur`, `Annonce`, `AnnoncePhoto`) ajoutée à `core/src`. Un formulaire Django unique (`AnnonceForm`) gère tous les champs ; la vue (`AnnonceCreateView`) gère la logique de sauvegarde (création du vendeur si besoin, statut selon le bouton cliqué, photos). Le wizard visuel est un unique template avec navigation JS entre 4 blocs — pas de librairie de wizard, pas de requête multiple.

**Tech Stack:** Django (déjà en place), Pillow (déjà réinstallé dans `requirements.txt`), Tailwind via CDN + JS vanilla (mêmes conventions que `connexion_admin.html`/`dashboard_admin.html`), tests via `django.test.TestCase` (aucune dépendance de test supplémentaire).

**Référence :** design complet dans `docs/superpowers/specs/2026-08-26-publication-annonce-vehicule-design.md`.

---

## Avant de commencer

Toutes les commandes ci-dessous s'exécutent depuis `core/src/` (là où se trouve `manage.py`). `DJANGO_SETTINGS_MODULE=core.settings` est déjà géré par `manage.py`.

Pillow est déjà présent dans `core/requirements.txt` (`pillow==12.3.0`) et déjà installé (`python -c "import PIL; print(PIL.__version__)"` fonctionne) — aucune action nécessaire sur ce point, contrairement à ce que le design supposait initialement.

---

### Task 1: Créer et enregistrer l'app Django `annonces`

**Files:**
- Create: `core/src/annonces/__init__.py`
- Create: `core/src/annonces/apps.py`
- Create: `core/src/annonces/migrations/__init__.py`
- Modify: `core/src/core/settings.py:27-29`

- [ ] **Step 1: Créer le squelette du package `annonces`**

Créer `core/src/annonces/__init__.py` (fichier vide).

Créer `core/src/annonces/apps.py` :

```python
from django.apps import AppConfig


class AnnoncesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'annonces'
```

Créer `core/src/annonces/migrations/__init__.py` (fichier vide).

- [ ] **Step 2: Enregistrer l'app dans `LOCAL_APPS`**

Dans `core/src/core/settings.py`, remplacer :

```python
LOCAL_APPS = [
    'app',
]
```

par :

```python
LOCAL_APPS = [
    'app',
    'annonces',
]
```

- [ ] **Step 3: Vérifier que Django reconnaît l'app**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add core/src/annonces/__init__.py core/src/annonces/apps.py core/src/annonces/migrations/__init__.py core/src/core/settings.py
git commit -m "feat(annonces): créer le squelette de l'app annonces"
```

---

### Task 2: Modèle `Vendeur` (TDD)

**Files:**
- Create: `core/src/annonces/models.py`
- Create: `core/src/annonces/tests/__init__.py`
- Create: `core/src/annonces/tests/test_models.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `core/src/annonces/tests/__init__.py` (fichier vide).

Créer `core/src/annonces/tests/test_models.py` :

```python
from django.test import TestCase

from annonces.models import Vendeur


class VendeurModelTest(TestCase):
    def test_create_vendeur_defaults_to_particulier(self):
        vendeur = Vendeur.objects.create(
            nom='Koffi Alain',
            telephone='+225 07 00 00 00 00',
        )
        self.assertEqual(vendeur.type, Vendeur.Type.PARTICULIER)
        self.assertEqual(str(vendeur), 'Koffi Alain')

    def test_db_table_is_explicit(self):
        self.assertEqual(Vendeur._meta.db_table, 'vendeurs')
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `ModuleNotFoundError` ou `ImportError: cannot import name 'Vendeur' from 'annonces.models'` (le fichier `models.py` n'existe pas encore)

- [ ] **Step 3: Créer le modèle `Vendeur`**

Créer `core/src/annonces/models.py` :

```python
from django.db import models


class Vendeur(models.Model):
    class Type(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.PARTICULIER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vendeurs'

    def __str__(self):
        return self.nom
```

- [ ] **Step 4: Créer et appliquer la migration**

Run: `python manage.py makemigrations annonces`
Expected: `Migrations for 'annonces': ... - Create model Vendeur`

Run: `python manage.py migrate annonces`
Expected: `Applying annonces.0001_initial... OK`

- [ ] **Step 5: Lancer le test et vérifier qu'il passe**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `OK` (2 tests passent)

- [ ] **Step 6: Commit**

```bash
git add core/src/annonces/models.py core/src/annonces/migrations/ core/src/annonces/tests/
git commit -m "feat(annonces): ajouter le modèle Vendeur"
```

---

### Task 3: Modèle `Annonce` (TDD)

**Files:**
- Modify: `core/src/annonces/models.py`
- Modify: `core/src/annonces/tests/test_models.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `core/src/annonces/tests/test_models.py` :

```python
from annonces.models import Annonce  # noqa: E402  (ajouter en haut du fichier, voir ci-dessous)


class AnnonceModelTest(TestCase):
    def setUp(self):
        self.vendeur = Vendeur.objects.create(nom='Koffi Alain', telephone='0700000000')

    def _create_annonce(self, **overrides):
        defaults = dict(
            vendeur=self.vendeur,
            marque='Toyota',
            modele='RAV4',
            annee=2022,
            prix=18500000,
            kilometrage=45000,
            carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE,
            couleur='Blanc',
            description='Très bon état, entretien à jour.',
        )
        defaults.update(overrides)
        return Annonce.objects.create(**defaults)

    def test_create_annonce_defaults_to_brouillon_and_unpublished(self):
        annonce = self._create_annonce()
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertFalse(annonce.publish)
        self.assertEqual(str(annonce), 'Toyota RAV4 (2022)')

    def test_save_sets_publish_true_when_statut_publiee(self):
        annonce = self._create_annonce(statut=Annonce.Statut.PUBLIEE)
        self.assertTrue(annonce.publish)

    def test_save_sets_publish_false_when_statut_changes_away_from_publiee(self):
        annonce = self._create_annonce(statut=Annonce.Statut.PUBLIEE)
        annonce.statut = Annonce.Statut.REFUSEE
        annonce.save()
        self.assertFalse(annonce.publish)

    def test_db_table_is_explicit(self):
        self.assertEqual(Annonce._meta.db_table, 'annonces')
```

Remplacer la ligne d'import en haut du fichier (`from annonces.models import Vendeur`) par :

```python
from annonces.models import Annonce, Vendeur
```

et supprimer la ligne `from annonces.models import Annonce  # noqa: E402` insérée au milieu du fichier (c'était un repère temporaire — l'import doit être unique, en haut du fichier).

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `ImportError: cannot import name 'Annonce' from 'annonces.models'`

- [ ] **Step 3: Créer le modèle `Annonce`**

Remplacer le contenu de `core/src/annonces/models.py` par :

```python
from django.db import models

from app.models import Convention


class Vendeur(models.Model):
    class Type(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.PARTICULIER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vendeurs'

    def __str__(self):
        return self.nom


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

    vendeur = models.ForeignKey(Vendeur, on_delete=models.PROTECT, related_name='annonces')
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    annee = models.PositiveIntegerField()
    prix = models.PositiveIntegerField()
    kilometrage = models.PositiveIntegerField()
    carburant = models.CharField(max_length=20, choices=Carburant.choices)
    boite_vitesses = models.CharField(max_length=20, choices=BoiteVitesses.choices)
    couleur = models.CharField(max_length=50)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)

    class Meta:
        db_table = 'annonces'

    def __str__(self):
        return f'{self.marque} {self.modele} ({self.annee})'

    def save(self, *args, **kwargs):
        self.publish = self.statut == self.Statut.PUBLIEE
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Créer et appliquer la migration**

Run: `python manage.py makemigrations annonces`
Expected: `Migrations for 'annonces': ... - Create model Annonce`

Run: `python manage.py migrate annonces`
Expected: `Applying annonces.0002_annonce... OK`

- [ ] **Step 5: Lancer les tests et vérifier qu'ils passent**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `OK` (6 tests passent)

- [ ] **Step 6: Commit**

```bash
git add core/src/annonces/models.py core/src/annonces/migrations/ core/src/annonces/tests/test_models.py
git commit -m "feat(annonces): ajouter le modèle Annonce avec workflow de statut"
```

---

### Task 4: Modèle `AnnoncePhoto` + admin Django (TDD)

**Files:**
- Modify: `core/src/annonces/models.py`
- Modify: `core/src/annonces/tests/test_models.py`
- Create: `core/src/annonces/admin.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter en haut de `core/src/annonces/tests/test_models.py`, sous les imports existants :

```python
from django.core.files.uploadedfile import SimpleUploadedFile

# 1x1 pixel GIF valide — le plus petit fichier image reconnu par Pillow/ImageField
GIF_1PX = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04'
    b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)
```

Ajouter à la fin du fichier :

```python
class AnnoncePhotoModelTest(TestCase):
    def test_create_annonce_photo(self):
        vendeur = Vendeur.objects.create(nom='Koffi Alain', telephone='0700000000')
        annonce = Annonce.objects.create(
            vendeur=vendeur, marque='Toyota', modele='RAV4', annee=2022,
            prix=18500000, kilometrage=45000, carburant=Annonce.Carburant.ESSENCE,
            boite_vitesses=Annonce.BoiteVitesses.AUTOMATIQUE, couleur='Blanc',
            description='Très bon état.',
        )
        image = SimpleUploadedFile('photo.gif', GIF_1PX, content_type='image/gif')

        photo = AnnoncePhoto.objects.create(annonce=annonce, image=image, ordre=0)

        self.assertEqual(photo.annonce, annonce)
        self.assertEqual(list(annonce.photos.all()), [photo])

    def test_db_table_is_explicit(self):
        self.assertEqual(AnnoncePhoto._meta.db_table, 'annonce_photos')
```

Mettre à jour l'import en haut du fichier :

```python
from annonces.models import Annonce, AnnoncePhoto, Vendeur
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `ImportError: cannot import name 'AnnoncePhoto' from 'annonces.models'`

- [ ] **Step 3: Ajouter le modèle `AnnoncePhoto`**

Ajouter à la fin de `core/src/annonces/models.py` :

```python
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

- [ ] **Step 4: Créer et appliquer la migration**

Run: `python manage.py makemigrations annonces`
Expected: `Migrations for 'annonces': ... - Create model AnnoncePhoto`

Run: `python manage.py migrate annonces`
Expected: `Applying annonces.0003_annoncephoto... OK`

- [ ] **Step 5: Lancer les tests et vérifier qu'ils passent**

Run: `python manage.py test annonces.tests.test_models -v 2`
Expected: `OK` (8 tests passent)

- [ ] **Step 6: Enregistrer les modèles dans l'admin Django**

Créer `core/src/annonces/admin.py` :

```python
from django.contrib import admin

from .models import Annonce, AnnoncePhoto, Vendeur

admin.site.register(Vendeur)
admin.site.register(Annonce)
admin.site.register(AnnoncePhoto)
```

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 7: Commit**

```bash
git add core/src/annonces/models.py core/src/annonces/admin.py core/src/annonces/migrations/ core/src/annonces/tests/test_models.py
git commit -m "feat(annonces): ajouter le modèle AnnoncePhoto et l'admin Django"
```

---

### Task 5: `AnnonceForm` (TDD)

**Files:**
- Create: `core/src/annonces/forms.py`
- Create: `core/src/annonces/tests/test_forms.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `core/src/annonces/tests/test_forms.py` :

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from annonces.forms import AnnonceForm
from annonces.models import Vendeur

GIF_1PX = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04'
    b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def valid_annonce_data(**overrides):
    data = dict(
        marque='Toyota', modele='RAV4', annee=2022, prix=18500000,
        kilometrage=45000, carburant='essence', boite_vitesses='automatique',
        couleur='Blanc', description='Très bon état.',
    )
    data.update(overrides)
    return data


class AnnonceFormTest(TestCase):
    def setUp(self):
        self.vendeur = Vendeur.objects.create(nom='Koffi Alain', telephone='0700000000')

    def test_valid_with_existing_vendeur(self):
        form = AnnonceForm(data=valid_annonce_data(vendeur_existant=self.vendeur.pk))
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_new_vendeur(self):
        form = AnnonceForm(data=valid_annonce_data(
            nouveau_vendeur_nom='Marie Diallo',
            nouveau_vendeur_telephone='0711111111',
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_without_any_vendeur(self):
        form = AnnonceForm(data=valid_annonce_data())
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_invalid_with_more_than_eight_photos(self):
        files = MultiValueDict({
            'photos': [
                SimpleUploadedFile(f'photo{i}.gif', GIF_1PX, content_type='image/gif')
                for i in range(9)
            ]
        })
        form = AnnonceForm(
            data=valid_annonce_data(vendeur_existant=self.vendeur.pk),
            files=files,
        )
        self.assertFalse(form.is_valid())

    def test_valid_with_eight_photos(self):
        files = MultiValueDict({
            'photos': [
                SimpleUploadedFile(f'photo{i}.gif', GIF_1PX, content_type='image/gif')
                for i in range(8)
            ]
        })
        form = AnnonceForm(
            data=valid_annonce_data(vendeur_existant=self.vendeur.pk),
            files=files,
        )
        self.assertTrue(form.is_valid(), form.errors)
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `python manage.py test annonces.tests.test_forms -v 2`
Expected: `ModuleNotFoundError: No module named 'annonces.forms'`

- [ ] **Step 3: Créer `AnnonceForm`**

Créer `core/src/annonces/forms.py` :

```python
from django import forms

from .models import Annonce, Vendeur


class AnnonceForm(forms.ModelForm):
    vendeur_existant = forms.ModelChoiceField(
        queryset=Vendeur.objects.all(),
        required=False,
        label='Vendeur existant',
    )
    nouveau_vendeur_nom = forms.CharField(max_length=150, required=False, label='Nom du nouveau vendeur')
    nouveau_vendeur_telephone = forms.CharField(max_length=30, required=False, label='Téléphone')
    nouveau_vendeur_email = forms.EmailField(required=False, label='Email')
    nouveau_vendeur_type = forms.ChoiceField(
        choices=Vendeur.Type.choices,
        required=False,
        initial=Vendeur.Type.PARTICULIER,
        label='Type de vendeur',
    )

    class Meta:
        model = Annonce
        fields = [
            'marque', 'modele', 'annee', 'prix',
            'kilometrage', 'carburant', 'boite_vitesses', 'couleur',
            'description',
        ]

    def clean(self):
        cleaned_data = super().clean()
        vendeur_existant = cleaned_data.get('vendeur_existant')
        nom = cleaned_data.get('nouveau_vendeur_nom')
        telephone = cleaned_data.get('nouveau_vendeur_telephone')

        if not vendeur_existant and not (nom and telephone):
            raise forms.ValidationError(
                "Sélectionnez un vendeur existant ou renseignez au moins le nom "
                "et le téléphone du nouveau vendeur."
            )

        photos = self.files.getlist('photos') if self.files else []
        if len(photos) > 8:
            raise forms.ValidationError("Vous ne pouvez pas ajouter plus de 8 photos.")

        return cleaned_data
```

- [ ] **Step 4: Lancer les tests et vérifier qu'ils passent**

Run: `python manage.py test annonces.tests.test_forms -v 2`
Expected: `OK` (5 tests passent)

- [ ] **Step 5: Commit**

```bash
git add core/src/annonces/forms.py core/src/annonces/tests/test_forms.py
git commit -m "feat(annonces): ajouter AnnonceForm avec logique vendeur existant/nouveau"
```

---

### Task 6: `AnnonceCreateView`, URLs et template minimal (TDD)

**Files:**
- Create: `core/src/annonces/views.py`
- Create: `core/src/annonces/urls.py`
- Create: `core/src/templates/annonces/annonce_form.html`
- Create: `core/src/annonces/tests/test_views.py`
- Create: `core/src/app/tests.py`
- Modify: `core/src/core/urls.py`
- Modify: `core/src/app/views.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `core/src/annonces/tests/test_views.py` :

```python
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from annonces.models import Annonce, Vendeur

GIF_1PX = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04'
    b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)

User = get_user_model()


def valid_post_data(**overrides):
    data = dict(
        marque='Toyota', modele='RAV4', annee=2022, prix=18500000,
        kilometrage=45000, carburant='essence', boite_vitesses='automatique',
        couleur='Blanc', description='Très bon état.',
        nouveau_vendeur_nom='Marie Diallo', nouveau_vendeur_telephone='0711111111',
        action='brouillon',
    )
    data.update(overrides)
    return data


class AnnonceCreateViewAccessTest(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, f"/connexion/?next={reverse('annonce_creer')}")

    def test_non_staff_is_redirected_to_login(self):
        User.objects.create_user(username='client', password='motdepasse123', is_staff=False)
        self.client.login(username='client', password='motdepasse123')
        response = self.client.get(reverse('annonce_creer'))
        self.assertRedirects(response, f"/connexion/?next={reverse('annonce_creer')}")

    def test_staff_can_view_form(self):
        User.objects.create_user(username='staff', password='motdepasse123', is_staff=True)
        self.client.login(username='staff', password='motdepasse123')
        response = self.client.get(reverse('annonce_creer'))
        self.assertEqual(response.status_code, 200)


class AnnonceCreateViewPostTest(TestCase):
    def setUp(self):
        self.vendeur = Vendeur.objects.create(nom='Koffi Alain', telephone='0700000000')
        User.objects.create_user(username='staff', password='motdepasse123', is_staff=True)
        self.client.login(username='staff', password='motdepasse123')

    def test_post_with_new_vendeur_creates_vendeur_and_annonce_as_brouillon(self):
        response = self.client.post(reverse('annonce_creer'), data=valid_post_data())

        self.assertRedirects(response, reverse('dashboard_admin'))
        annonce = Annonce.objects.get(marque='Toyota')
        self.assertEqual(annonce.statut, Annonce.Statut.BROUILLON)
        self.assertEqual(annonce.vendeur.nom, 'Marie Diallo')

    def test_post_with_existing_vendeur_reuses_it(self):
        response = self.client.post(
            reverse('annonce_creer'),
            data=valid_post_data(
                vendeur_existant=self.vendeur.pk,
                nouveau_vendeur_nom='', nouveau_vendeur_telephone='',
            ),
        )

        self.assertRedirects(response, reverse('dashboard_admin'))
        annonce = Annonce.objects.get(marque='Toyota')
        self.assertEqual(annonce.vendeur, self.vendeur)
        self.assertEqual(Vendeur.objects.count(), 1)

    def test_post_with_action_soumettre_sets_en_attente(self):
        self.client.post(
            reverse('annonce_creer'),
            data=valid_post_data(vendeur_existant=self.vendeur.pk, action='soumettre'),
        )

        annonce = Annonce.objects.get(marque='Toyota')
        self.assertEqual(annonce.statut, Annonce.Statut.EN_ATTENTE)

    def test_post_with_photos_creates_ordered_annonce_photos(self):
        data = valid_post_data(vendeur_existant=self.vendeur.pk)
        data['photos'] = [
            SimpleUploadedFile('a.gif', GIF_1PX, content_type='image/gif'),
            SimpleUploadedFile('b.gif', GIF_1PX, content_type='image/gif'),
        ]

        self.client.post(reverse('annonce_creer'), data=data)

        annonce = Annonce.objects.get(marque='Toyota')
        photos = list(annonce.photos.order_by('ordre'))
        self.assertEqual(len(photos), 2)
        self.assertEqual([p.ordre for p in photos], [0, 1])

    def test_post_missing_vendeur_redisplays_form_without_saving(self):
        data = valid_post_data()
        data['nouveau_vendeur_nom'] = ''
        data['nouveau_vendeur_telephone'] = ''

        response = self.client.post(reverse('annonce_creer'), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Annonce.objects.filter(marque='Toyota').exists())

    def test_post_too_many_photos_redisplays_form_without_saving(self):
        data = valid_post_data(vendeur_existant=self.vendeur.pk)
        data['photos'] = [
            SimpleUploadedFile(f'{i}.gif', GIF_1PX, content_type='image/gif') for i in range(9)
        ]

        response = self.client.post(reverse('annonce_creer'), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Annonce.objects.filter(marque='Toyota').exists())
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `python manage.py test annonces.tests.test_views -v 2`
Expected: `django.urls.exceptions.NoReverseMatch: Reverse for 'annonce_creer' not found`

- [ ] **Step 3: Créer un template minimal (sans le wizard visuel — ajouté en Task 7)**

Créer `core/src/templates/annonces/annonce_form.html` :

```html
{% extends 'app/base/base.html' %}

{% block title %}Nouvelle annonce — Portail Admin{% endblock %}

{% block content %}
<div class="p-8">
{% if form.non_field_errors %}
<p>{{ form.non_field_errors.0 }}</p>
{% endif %}
<form enctype="multipart/form-data" method="post">
{% csrf_token %}
{{ form.as_p }}
<input accept="image/*" multiple name="photos" type="file">
<button name="action" type="submit" value="brouillon">Enregistrer comme brouillon</button>
<button name="action" type="submit" value="soumettre">Soumettre pour validation</button>
</form>
</div>
{% endblock %}
```

- [ ] **Step 4: Créer la vue**

Créer `core/src/annonces/views.py` :

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.views import View

from .forms import AnnonceForm
from .models import Annonce, AnnoncePhoto, Vendeur


class AnnonceCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'annonces/annonce_form.html'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        # Par défaut, UserPassesTestMixin renvoie un 403 pour un utilisateur
        # déjà connecté qui échoue test_func (seul un utilisateur anonyme est
        # redirigé). On force la redirection dans les deux cas, comme prévu
        # par le design (section 5 du spec).
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )

    def get(self, request):
        return render(request, self.template_name, {'form': AnnonceForm()})

    def post(self, request):
        form = AnnonceForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        vendeur = form.cleaned_data.get('vendeur_existant')
        if vendeur is None:
            vendeur = Vendeur.objects.create(
                nom=form.cleaned_data['nouveau_vendeur_nom'],
                telephone=form.cleaned_data['nouveau_vendeur_telephone'],
                email=form.cleaned_data.get('nouveau_vendeur_email', ''),
                type=form.cleaned_data.get('nouveau_vendeur_type') or Vendeur.Type.PARTICULIER,
            )

        annonce = form.save(commit=False)
        annonce.vendeur = vendeur
        action = request.POST.get('action')
        annonce.statut = Annonce.Statut.EN_ATTENTE if action == 'soumettre' else Annonce.Statut.BROUILLON
        annonce.save()

        for index, photo in enumerate(request.FILES.getlist('photos')):
            AnnoncePhoto.objects.create(annonce=annonce, image=photo, ordre=index)

        messages.success(request, 'Annonce enregistrée avec succès.')
        return redirect('dashboard_admin')
```

- [ ] **Step 5: Créer les URLs de l'app et les inclure**

Créer `core/src/annonces/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
]
```

Dans `core/src/core/urls.py`, remplacer :

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

- [ ] **Step 6: Corriger le même problème sur `AdminDashboardView` (déjà en production, jamais testé pour ce cas)**

`AdminDashboardView` (`core/src/app/views.py`) utilise le même combo `LoginRequiredMixin` + `UserPassesTestMixin` que `AnnonceCreateView`. Avec `UserPassesTestMixin` seul, un utilisateur **déjà connecté** mais non-staff reçoit une erreur 403 au lieu d'être redirigé vers `/connexion/` — ce bug existant n'avait jamais été détecté car ce cas précis n'était pas testé. On l'aligne ici sur le même comportement, pour rester cohérent avec le spec (« même comportement que le dashboard »).

Créer `core/src/app/tests.py` :

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AdminDashboardViewAccessTest(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('dashboard_admin')}")

    def test_non_staff_is_redirected_to_login(self):
        User.objects.create_user(username='client', password='motdepasse123', is_staff=False)
        self.client.login(username='client', password='motdepasse123')
        response = self.client.get(reverse('dashboard_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('dashboard_admin')}")

    def test_staff_can_view_dashboard(self):
        User.objects.create_user(username='staff', password='motdepasse123', is_staff=True)
        self.client.login(username='staff', password='motdepasse123')
        response = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(response.status_code, 200)
```

Run: `python manage.py test app -v 2`
Expected: `FAIL` sur `test_non_staff_is_redirected_to_login` — `AssertionError: 403 != 302` (confirme le bug avant correction)

Dans `core/src/app/views.py`, remplacer :

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.views.generic import TemplateView
```

par :

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, redirect_to_login
from django.shortcuts import render
from django.views.generic import TemplateView
```

puis remplacer :

```python
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'app/layout/dashboard_admin.html'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff
```

par :

```python
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'app/layout/dashboard_admin.html'
    login_url = 'connexion_admin'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )
```

Run: `python manage.py test app -v 2`
Expected: `OK` (3 tests passent)

- [ ] **Step 7: Lancer les tests de la vue `AnnonceCreateView` et vérifier qu'ils passent**

Run: `python manage.py test annonces.tests.test_views -v 2`
Expected: `OK` (9 tests passent)

- [ ] **Step 8: Lancer toute la suite de tests de l'app `annonces`**

Run: `python manage.py test annonces -v 2`
Expected: `OK` (22 tests passent : 8 modèles + 5 formulaire + 9 vue)

- [ ] **Step 9: Commit**

```bash
git add core/src/annonces/views.py core/src/annonces/urls.py core/src/annonces/tests/test_views.py core/src/templates/annonces/annonce_form.html core/src/core/urls.py core/src/app/views.py core/src/app/tests.py
git commit -m "feat(annonces): ajouter AnnonceCreateView, les URLs et un template minimal

Corrige au passage AdminDashboardView (app/views.py) qui avait le même
bug non détecté : un utilisateur connecté mais non-staff recevait un
403 au lieu d'être redirigé vers la connexion."
```

---

### Task 7: Wizard visuel en 4 étapes (remplace le template minimal)

**Files:**
- Modify: `core/src/templates/annonces/annonce_form.html`
- Modify: `core/src/annonces/tests/test_views.py`

- [ ] **Step 1: Ajouter un test qui échoue pour la structure du wizard**

Ajouter à la fin de la classe `AnnonceCreateViewAccessTest` dans `core/src/annonces/tests/test_views.py` :

```python
    def test_staff_view_contains_all_wizard_steps(self):
        User.objects.create_user(username='staff2', password='motdepasse123', is_staff=True)
        self.client.login(username='staff2', password='motdepasse123')
        response = self.client.get(reverse('annonce_creer'))
        for step in ['1', '2', '3', '4']:
            self.assertContains(response, f'data-step="{step}"')
        self.assertContains(response, 'name="photos"')
        self.assertContains(response, 'value="brouillon"')
        self.assertContains(response, 'value="soumettre"')
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `python manage.py test annonces.tests.test_views.AnnonceCreateViewAccessTest.test_staff_view_contains_all_wizard_steps -v 2`
Expected: `FAIL` — le template minimal ne contient pas d'attributs `data-step`

- [ ] **Step 3: Remplacer le template par le wizard complet**

Remplacer tout le contenu de `core/src/templates/annonces/annonce_form.html` par :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Nouvelle annonce — Portail Admin{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary-fixed":"#cbe6ff","on-primary-fixed-variant":"#0e4b6e","surface-container-lowest":"#ffffff","on-primary-container":"#94c5ee","outline-variant":"#c1c7cf","primary":"#003b5a","on-tertiary-container":"#aec1d8","inverse-on-surface":"#f0f1f1","on-secondary-fixed-variant":"#663e00","surface":"#f8f9f9","secondary-container":"#fea520","surface-container-high":"#e7e8e8","background":"#f8f9f9","surface-dim":"#d9dada","on-secondary":"#ffffff","inverse-primary":"#9bccf6","on-error-container":"#93000a","on-primary-fixed":"#001e30","on-secondary-container":"#694000","on-tertiary":"#ffffff","tertiary":"#26384b","secondary-fixed":"#ffddb9","tertiary-container":"#3d4f63","surface-variant":"#e1e3e3","surface-container-highest":"#e1e3e3","secondary-fixed-dim":"#ffb961","surface-container":"#edeeee","inverse-surface":"#2e3131","primary-fixed-dim":"#9bccf6","surface-container-low":"#f3f4f4","surface-bright":"#f8f9f9","on-error":"#ffffff","on-background":"#191c1c","tertiary-fixed":"#d1e4fc","outline":"#72787f","error-container":"#ffdad6","on-surface":"#191c1c","on-surface-variant":"#41474e","on-secondary-fixed":"#2b1700","error":"#ba1a1a","surface-tint":"#2f6388","primary-container":"#1a5276","on-tertiary-fixed":"#091d2e","tertiary-fixed-dim":"#b5c8e0","on-primary":"#ffffff","secondary":"#865300","on-tertiary-fixed-variant":"#36485c"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem","xl":"0.75rem","full":"9999px"},"spacing":{"container-margin-desktop":"32px","section-gap":"48px","container-margin-mobile":"16px","base":"8px","gutter":"16px"},"fontFamily":{"label-sm":["Inter"],"headline-lg-mobile":["Montserrat"],"display-lg":["Montserrat"],"headline-lg":["Montserrat"],"body-lg":["Inter"],"body-md":["Inter"],"headline-md":["Montserrat"],"label-md":["Inter"]},"fontSize":{"label-sm":["10px",{"lineHeight":"14px","fontWeight":"500"}],"headline-lg-mobile":["18px",{"lineHeight":"24px","fontWeight":"700"}],"display-lg":["26px",{"lineHeight":"32px","letterSpacing":"-0.02em","fontWeight":"700"}],"headline-lg":["22px",{"lineHeight":"28px","fontWeight":"700"}],"body-lg":["14px",{"lineHeight":"20px","fontWeight":"400"}],"body-md":["13px",{"lineHeight":"18px","fontWeight":"400"}],"headline-md":["15px",{"lineHeight":"20px","fontWeight":"600"}],"label-md":["11px",{"lineHeight":"16px","letterSpacing":"0.01em","fontWeight":"600"}]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100..900&amp;family=Montserrat:wght@100..900&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface">
<!-- En-tête mobile/tablette (< lg) -->
<header class="lg:hidden fixed top-0 inset-x-0 z-50 h-16 pt-safe bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center gap-3 px-container-margin-mobile">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<h1 class="font-headline-md text-headline-md text-primary">Nouvelle annonce</h1>
</header>
<!-- Sidebar desktop (lg+) -->
<aside class="hidden lg:flex fixed left-0 top-0 h-full w-72 bg-primary text-on-primary z-50 flex-col shadow-xl">
<div class="p-gutter flex items-center gap-3 mb-section-gap">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<span class="font-headline-md text-headline-md tracking-tight">Djona Admin</span>
</div>
<nav class="flex-1 px-4 flex flex-col gap-base">
<a aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm" href="{% url 'annonce_creer' %}">
<span class="material-symbols-outlined mr-4">add_circle</span><span class="font-label-md text-label-md">Nouvelle annonce</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined mr-4">dashboard</span><span class="font-label-md text-label-md">Dashboard</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Validation Queue</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Users</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">receipt_long</span><span class="font-label-md text-label-md">Transactions</span>
</a>
<div class="mt-auto mb-4 border-t border-on-primary/10 pt-4">
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'admin:index' %}">
<span class="material-symbols-outlined mr-4">settings</span><span class="font-label-md text-label-md">Settings</span>
</a>
<form action="{% url 'deconnexion_admin' %}" method="post">
{% csrf_token %}
<button class="w-full flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" type="submit">
<span class="material-symbols-outlined mr-4">logout</span><span class="font-label-md text-label-md">Déconnexion</span>
</button>
</form>
</div>
</nav>
</aside>
<div class="lg:pl-72">
<header class="hidden lg:flex fixed top-0 left-72 right-0 h-16 bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-40 items-center px-container-margin-desktop">
<h1 class="font-headline-md text-headline-md text-primary">Nouvelle annonce</h1>
</header>
<main class="relative pt-16 pb-8 bg-surface min-h-screen px-container-margin-mobile md:px-container-margin-desktop">

<div class="flex items-center justify-between max-w-3xl mx-auto py-6 gap-2">
<span data-step-indicator="1" class="font-label-md text-label-md text-primary font-bold">① Infos</span>
<span class="flex-1 h-px bg-outline-variant"></span>
<span data-step-indicator="2" class="font-label-md text-label-md text-on-surface-variant">② Caractéristiques</span>
<span class="flex-1 h-px bg-outline-variant"></span>
<span data-step-indicator="3" class="font-label-md text-label-md text-on-surface-variant">③ Photos</span>
<span class="flex-1 h-px bg-outline-variant"></span>
<span data-step-indicator="4" class="font-label-md text-label-md text-on-surface-variant">④ Publication</span>
</div>

{% if form.non_field_errors %}
<div class="max-w-3xl mx-auto mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container font-label-sm text-label-sm">
{{ form.non_field_errors.0 }}
</div>
{% endif %}

<form method="post" enctype="multipart/form-data" class="max-w-3xl mx-auto bg-surface-container-lowest rounded-2xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] p-6 md:p-8 flex flex-col gap-6">
{% csrf_token %}

<div data-step="1" class="flex flex-col gap-4">
<h2 class="font-headline-md text-headline-md text-primary">Informations générales</h2>

<div class="flex flex-col gap-1 {% if form.marque.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.marque.id_for_label }}">Marque</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.marque.id_for_label }}" name="marque" required type="text" value="{{ form.marque.value|default:'' }}">
{% if form.marque.errors %}<p class="text-[11px] text-error">{{ form.marque.errors.0 }}</p>{% endif %}
</div>

<div class="flex flex-col gap-1 {% if form.modele.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.modele.id_for_label }}">Modèle</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.modele.id_for_label }}" name="modele" required type="text" value="{{ form.modele.value|default:'' }}">
{% if form.modele.errors %}<p class="text-[11px] text-error">{{ form.modele.errors.0 }}</p>{% endif %}
</div>

<div class="grid grid-cols-2 gap-4">
<div class="flex flex-col gap-1 {% if form.annee.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.annee.id_for_label }}">Année</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.annee.id_for_label }}" min="1980" name="annee" required type="number" value="{{ form.annee.value|default:'' }}">
{% if form.annee.errors %}<p class="text-[11px] text-error">{{ form.annee.errors.0 }}</p>{% endif %}
</div>
<div class="flex flex-col gap-1 {% if form.prix.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.prix.id_for_label }}">Prix (CFA)</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.prix.id_for_label }}" min="0" name="prix" required type="number" value="{{ form.prix.value|default:'' }}">
{% if form.prix.errors %}<p class="text-[11px] text-error">{{ form.prix.errors.0 }}</p>{% endif %}
</div>
</div>

<div class="flex justify-end mt-2">
<button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-label-md flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
</div>
</div>

<div data-step="2" class="hidden flex flex-col gap-4">
<h2 class="font-headline-md text-headline-md text-primary">Caractéristiques</h2>

<div class="flex flex-col gap-1 {% if form.kilometrage.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.kilometrage.id_for_label }}">Kilométrage</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.kilometrage.id_for_label }}" min="0" name="kilometrage" required type="number" value="{{ form.kilometrage.value|default:'' }}">
{% if form.kilometrage.errors %}<p class="text-[11px] text-error">{{ form.kilometrage.errors.0 }}</p>{% endif %}
</div>

<div class="grid grid-cols-2 gap-4">
<div class="flex flex-col gap-1 {% if form.carburant.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.carburant.id_for_label }}">Carburant</label>
<select class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.carburant.id_for_label }}" name="carburant" required>
{% for value, label in form.fields.carburant.choices %}<option value="{{ value }}" {% if form.carburant.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
</select>
{% if form.carburant.errors %}<p class="text-[11px] text-error">{{ form.carburant.errors.0 }}</p>{% endif %}
</div>
<div class="flex flex-col gap-1 {% if form.boite_vitesses.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.boite_vitesses.id_for_label }}">Boîte de vitesses</label>
<select class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.boite_vitesses.id_for_label }}" name="boite_vitesses" required>
{% for value, label in form.fields.boite_vitesses.choices %}<option value="{{ value }}" {% if form.boite_vitesses.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
</select>
{% if form.boite_vitesses.errors %}<p class="text-[11px] text-error">{{ form.boite_vitesses.errors.0 }}</p>{% endif %}
</div>
</div>

<div class="flex flex-col gap-1 {% if form.couleur.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.couleur.id_for_label }}">Couleur</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.couleur.id_for_label }}" name="couleur" required type="text" value="{{ form.couleur.value|default:'' }}">
{% if form.couleur.errors %}<p class="text-[11px] text-error">{{ form.couleur.errors.0 }}</p>{% endif %}
</div>

<div class="flex justify-between mt-2">
<button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-label-md flex items-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
<button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-label-md flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
</div>
</div>

<div data-step="3" class="hidden flex flex-col gap-4">
<h2 class="font-headline-md text-headline-md text-primary">Photos</h2>
<p class="font-body-md text-body-md text-on-surface-variant">Jusqu'à 8 photos. <span id="photo-count">0/8</span></p>

<label class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-outline-variant rounded-lg py-8 cursor-pointer hover:border-primary transition-colors" for="id_photos">
<span class="material-symbols-outlined text-primary text-[32px]">add_photo_alternate</span>
<span class="font-label-md text-label-md text-on-surface-variant">Ajouter des photos</span>
</label>
<input accept="image/*" class="hidden" id="id_photos" multiple name="photos" type="file">

<div class="grid grid-cols-3 sm:grid-cols-4 gap-3" id="photo-grid"></div>

<div class="flex justify-between mt-2">
<button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-label-md flex items-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
<button class="wizard-next px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-label-md flex items-center gap-2" type="button">Suivant <span class="material-symbols-outlined text-[18px]">arrow_forward</span></button>
</div>
</div>

<div data-step="4" class="hidden flex flex-col gap-4">
<h2 class="font-headline-md text-headline-md text-primary">Vendeur & publication</h2>

<div class="flex gap-4">
<label class="flex items-center gap-2 font-label-md text-label-md text-on-surface"><input checked name="vendeur_mode" type="radio" value="nouveau"> Nouveau vendeur</label>
<label class="flex items-center gap-2 font-label-md text-label-md text-on-surface"><input name="vendeur_mode" type="radio" value="existant"> Vendeur existant</label>
</div>

<div id="nouveau-vendeur-block" class="flex flex-col gap-4">
<div class="flex flex-col gap-1">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.nouveau_vendeur_nom.id_for_label }}">Nom</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.nouveau_vendeur_nom.id_for_label }}" name="nouveau_vendeur_nom" type="text" value="{{ form.nouveau_vendeur_nom.value|default:'' }}">
</div>
<div class="grid grid-cols-2 gap-4">
<div class="flex flex-col gap-1">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.nouveau_vendeur_telephone.id_for_label }}">Téléphone</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.nouveau_vendeur_telephone.id_for_label }}" name="nouveau_vendeur_telephone" type="text" value="{{ form.nouveau_vendeur_telephone.value|default:'' }}">
</div>
<div class="flex flex-col gap-1">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.nouveau_vendeur_email.id_for_label }}">Email (optionnel)</label>
<input class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.nouveau_vendeur_email.id_for_label }}" name="nouveau_vendeur_email" type="email" value="{{ form.nouveau_vendeur_email.value|default:'' }}">
</div>
</div>
<div class="flex flex-col gap-1">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.nouveau_vendeur_type.id_for_label }}">Type</label>
<select class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.nouveau_vendeur_type.id_for_label }}" name="nouveau_vendeur_type">
{% for value, label in form.fields.nouveau_vendeur_type.choices %}<option value="{{ value }}" {% if form.nouveau_vendeur_type.value == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
</select>
</div>
</div>

<div id="vendeur-existant-block" class="hidden flex flex-col gap-1">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.vendeur_existant.id_for_label }}">Vendeur</label>
<select class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.vendeur_existant.id_for_label }}" name="vendeur_existant">
<option value="">—</option>
{% for vendeur in form.fields.vendeur_existant.queryset %}<option value="{{ vendeur.pk }}" {% if form.vendeur_existant.value|stringformat:"s" == vendeur.pk|stringformat:"s" %}selected{% endif %}>{{ vendeur.nom }}</option>{% endfor %}
</select>
</div>

<div class="flex flex-col gap-1 {% if form.description.errors %}field-error{% endif %}">
<label class="font-label-md text-label-md text-on-surface-variant" for="{{ form.description.id_for_label }}">Description</label>
<textarea class="w-full px-4 py-3 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" id="{{ form.description.id_for_label }}" name="description" required rows="4">{{ form.description.value|default:'' }}</textarea>
{% if form.description.errors %}<p class="text-[11px] text-error">{{ form.description.errors.0 }}</p>{% endif %}
</div>

<div class="flex flex-col sm:flex-row justify-between gap-3 mt-2">
<button class="wizard-prev px-6 py-3 bg-surface-container text-on-surface rounded-lg font-label-md text-label-md flex items-center justify-center gap-2" type="button"><span class="material-symbols-outlined text-[18px]">arrow_back</span> Précédent</button>
<div class="flex flex-col sm:flex-row gap-3">
<button class="px-6 py-3 border-2 border-primary text-primary rounded-lg font-label-md text-label-md" name="action" type="submit" value="brouillon">Enregistrer comme brouillon</button>
<button class="px-6 py-3 bg-primary text-on-primary rounded-lg font-label-md text-label-md" name="action" type="submit" value="soumettre">Soumettre pour validation</button>
</div>
</div>
</div>

</form>
</main>
</div>
</div>
{% endblock %}

{% block scripts %}
<script>
(function () {
  var steps = Array.prototype.slice.call(document.querySelectorAll('[data-step]'));
  var indicators = Array.prototype.slice.call(document.querySelectorAll('[data-step-indicator]'));
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

  var vendeurModeRadios = document.querySelectorAll('input[name="vendeur_mode"]');
  var vendeurExistantBlock = document.getElementById('vendeur-existant-block');
  var nouveauVendeurBlock = document.getElementById('nouveau-vendeur-block');

  function applyVendeurMode(mode) {
    vendeurExistantBlock.classList.toggle('hidden', mode !== 'existant');
    nouveauVendeurBlock.classList.toggle('hidden', mode !== 'nouveau');
  }

  vendeurModeRadios.forEach(function (radio) {
    radio.addEventListener('change', function () { applyVendeurMode(radio.value); });
  });
  applyVendeurMode(document.querySelector('input[name="vendeur_mode"]:checked').value);

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
        '<button type="button" data-index="' + index + '" class="remove-photo absolute top-1 right-1 w-6 h-6 rounded-full bg-error text-on-error flex items-center justify-center">' +
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

- [ ] **Step 4: Lancer tous les tests de l'app et vérifier qu'ils passent**

Run: `python manage.py test annonces -v 2`
Expected: `OK` (23 tests passent — les 22 précédents + le nouveau test de structure du wizard)

- [ ] **Step 5: Commit**

```bash
git add core/src/templates/annonces/annonce_form.html core/src/annonces/tests/test_views.py
git commit -m "feat(annonces): wizard visuel en 4 étapes pour la création d'annonce"
```

---

### Task 8: Lien "Nouvelle annonce" dans le dashboard admin

**Files:**
- Modify: `core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Ajouter le lien dans la sidebar desktop**

Dans `core/src/templates/app/layout/dashboard_admin.html`, remplacer :

```html
<nav class="flex-1 px-4 flex flex-col gap-base">
<a aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined mr-4">dashboard</span><span class="font-label-md text-label-md">Dashboard</span>
</a>
```

par :

```html
<nav class="flex-1 px-4 flex flex-col gap-base">
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_creer' %}">
<span class="material-symbols-outlined mr-4">add_circle</span><span class="font-label-md text-label-md">Nouvelle annonce</span>
</a>
<a aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined mr-4">dashboard</span><span class="font-label-md text-label-md">Dashboard</span>
</a>
```

- [ ] **Step 2: Ajouter le lien dans la navigation basse mobile**

Dans le même fichier, remplacer :

```html
<a aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined">dashboard</span><span class="font-label-sm text-label-sm">Dashboard</span>
</a>
```

par :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_creer' %}">
<span class="material-symbols-outlined">add_circle</span><span class="font-label-sm text-label-sm">Annonce</span>
</a>
<a aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined">dashboard</span><span class="font-label-sm text-label-sm">Dashboard</span>
</a>
```

- [ ] **Step 3: Vérifier avec `manage.py check` qu'il n'y a pas d'erreur de template (URL introuvable, etc.)**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add core/src/templates/app/layout/dashboard_admin.html
git commit -m "feat(dashboard): ajouter le lien Nouvelle annonce dans la sidebar et la nav mobile"
```

---

### Task 9: Vérification manuelle bout-en-bout

**Files:** aucun (vérification uniquement)

- [ ] **Step 1: Lancer la suite de tests complète du projet**

Run: `python manage.py test`
Expected: `OK` (tous les tests passent, `annonces` inclus)

- [ ] **Step 2: Lancer le serveur de dev**

Run: `python manage.py runserver 127.0.0.1:8020` (en arrière-plan)

- [ ] **Step 3: Se connecter avec le superadmin (`admin` / `admin`) et vérifier le lien**

- Ouvrir `http://127.0.0.1:8020/connexion/`, se connecter.
- Sur `http://127.0.0.1:8020/tableau-de-bord/`, vérifier que le lien « Nouvelle annonce » (sidebar desktop et nav basse mobile) est présent et pointe vers `/annonces/creer/`.

- [ ] **Step 4: Parcourir le wizard de bout en bout dans le navigateur**

- Cliquer sur « Nouvelle annonce ».
- Étape 1 : remplir marque/modèle/année/prix, cliquer Suivant (vérifier qu'un champ vide bloque l'avancée).
- Étape 2 : remplir kilométrage/carburant/boîte/couleur, Suivant.
- Étape 3 : ajouter 2-3 photos, vérifier les miniatures et le compteur, en retirer une, Suivant.
- Étape 4 : laisser « Nouveau vendeur » sélectionné, remplir nom/téléphone, description, cliquer « Soumettre pour validation ».
- Vérifier la redirection vers le dashboard.

- [ ] **Step 5: Vérifier en base que tout est bien enregistré**

Run (dans un shell séparé, pendant que le serveur tourne) :

```bash
python manage.py shell -c "
from annonces.models import Annonce
a = Annonce.objects.latest('created_at')
print(a.marque, a.modele, a.statut, a.vendeur.nom, a.photos.count())
"
```

Expected: la dernière annonce créée, avec `statut == 'en_attente'` (ou `brouillon` selon le bouton cliqué) et `a.photos.count()` égal au nombre de photos ajoutées.

- [ ] **Step 6: Arrêter le serveur de dev**

Trouver et arrêter le processus `manage.py runserver` lancé à l'étape 2 (ex. `kill <PID>` ciblé — ne pas utiliser `taskkill /IM python.exe` qui tuerait tous les processus Python de la machine).

---

## Résumé des commits attendus

1. `feat(annonces): créer le squelette de l'app annonces`
2. `feat(annonces): ajouter le modèle Vendeur`
3. `feat(annonces): ajouter le modèle Annonce avec workflow de statut`
4. `feat(annonces): ajouter le modèle AnnoncePhoto et l'admin Django`
5. `feat(annonces): ajouter AnnonceForm avec logique vendeur existant/nouveau`
6. `feat(annonces): ajouter AnnonceCreateView, les URLs et un template minimal`
7. `feat(annonces): wizard visuel en 4 étapes pour la création d'annonce`
8. `feat(dashboard): ajouter le lien Nouvelle annonce dans la sidebar et la nav mobile`

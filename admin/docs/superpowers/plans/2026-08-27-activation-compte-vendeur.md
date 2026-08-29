# Activation de compte vendeur — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un vendeur qui s'inscrit démarre en statut `en_attente` (connexion autorisée, dashboard limité) ; le dashboard admin liste tous les comptes vendeur et permet de les activer ou de les suspendre, via une connexion base de données directe vers le schéma `djona_vendor`.

**Architecture:** Ajout d'un champ `statut_compte` sur `vendor.app.Utilisateur`. Côté admin, une deuxième connexion `DATABASES['vendor_db']` pointe sur le même schéma, avec des modèles miroirs `managed=False` dans une nouvelle app `moderation`. Toutes les requêtes sur ces miroirs passent explicitement par `.using('vendor_db')`.

**Tech Stack:** Django 5.0.14, MySQL local (deux schémas, même serveur), python-decouple.

**Référence design complet :** `docs/superpowers/specs/2026-08-27-workflow-vendeur-admin-design.md`

---

## Contexte pour l'exécutant

Deux projets Django **séparés**, chacun avec son propre `manage.py`/venv :
- `vendor/core/src` (venv : `vendor/core/venv`) — le portail vendeur.
- `admin/core/src` (venv : `admin/core/venv`) — le portail admin.

Les deux se connectent au même serveur MySQL local (`127.0.0.1:3307`, utilisateur
`djona_app`), mais des schémas séparés : `djona_vendor` et `djona_admin`. Les
identifiants sont dans `vendor/core/.env` et `admin/core/.env` (déjà configurés,
`USE_MYSQL=True`).

Toute commande Django doit être lancée depuis le dossier `src/` du projet concerné, en
utilisant l'exécutable Python du venv de CE projet — par exemple, côté vendor :
```bash
cd vendor/core/src
../venv/Scripts/python.exe manage.py test
```

**Important — `manage.py test` côté admin nécessite `--keepdb` (à partir de la Task 4) :**
la connexion `vendor_db` (Task 3) pointe, en mode test, vers une base dédiée
`djona_vendor_test` — pas vers la vraie base `djona_vendor` (pour éviter toute
destruction de données réelles). Cette base de test est peuplée manuellement en
rejouant les migrations du projet vendor dessus (voir Task 4), pas par le test-runner
Django lui-même (les modèles miroirs sont `managed=False`). Sans `--keepdb`, Django
supprime et recrée `djona_vendor_test` à chaque run — vide, sans aucune table — et tout
test touchant `vendor_db` échoue avec « table doesn't exist ». Donc partout dans ce plan
où une commande dit `../venv/Scripts/python.exe manage.py test` **pour le projet
admin**, lancer en réalité `../venv/Scripts/python.exe manage.py test --keepdb`. Côté
vendor, `--keepdb` n'est pas nécessaire (pas de connexion secondaire).

---

## Task 1: `statut_compte` sur le modèle `Utilisateur` (vendor)

**Files:**
- Modify: `vendor/core/src/app/models.py`
- Modify: `vendor/core/src/app/admin.py`
- Modify: `vendor/core/src/app/tests.py`
- Create: `vendor/core/src/app/migrations/0002_utilisateur_statut_compte.py` (générée)

- [ ] **Step 1: Écrire le test qui échoue**

Dans `vendor/core/src/app/tests.py`, ajouter cette méthode à la classe
`UtilisateurModelTest` existante (juste après `test_create_user_hashes_password`) :

```python
    def test_new_user_starts_en_attente(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange',
            telephone='0102030405',
        )
        self.assertEqual(user.statut_compte, Utilisateur.StatutCompte.EN_ATTENTE)
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test app.tests.UtilisateurModelTest.test_new_user_starts_en_attente -v 2`
Expected: `AttributeError: 'Utilisateur' object has no attribute 'statut_compte'`

- [ ] **Step 3: Ajouter le champ au modèle**

Dans `vendor/core/src/app/models.py`, la classe `Utilisateur` actuelle est :

```python
class Utilisateur(AbstractBaseUser, PermissionsMixin):
    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10, validators=[telephone_validator])
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
```

Ajouter la classe `StatutCompte` juste après `TypeCompte`, et le champ juste après
`type_compte` :

```python
class Utilisateur(AbstractBaseUser, PermissionsMixin):
    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    class StatutCompte(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'

    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10, validators=[telephone_validator])
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    statut_compte = models.CharField(max_length=20, choices=StatutCompte.choices, default=StatutCompte.EN_ATTENTE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
```

(Le reste de la classe — `objects`, `USERNAME_FIELD`, `REQUIRED_FIELDS`, `Meta`,
`__str__`, `get_full_name`, `get_short_name` — ne change pas.)

- [ ] **Step 4: Générer et appliquer la migration**

Run:
```bash
cd vendor/core/src
../venv/Scripts/python.exe manage.py makemigrations app
```
Expected: `Migrations for 'app': app\migrations\0002_utilisateur_statut_compte.py - Add field statut_compte to utilisateur`

Run:
```bash
../venv/Scripts/python.exe manage.py migrate
```
Expected: `Applying app.0002_utilisateur_statut_compte... OK`

- [ ] **Step 5: Vérifier que le test passe**

Run: `../venv/Scripts/python.exe manage.py test app.tests.UtilisateurModelTest.test_new_user_starts_en_attente -v 2`
Expected: PASS

- [ ] **Step 6: Mettre à jour l'admin Django du projet vendor**

Dans `vendor/core/src/app/admin.py`, remplacer :

```python
    list_display = ['email', 'nom', 'prenom', 'telephone', 'type_compte', 'is_active', 'date_joined']
    list_filter = ['type_compte', 'is_active', 'is_staff']
    search_fields = ['email', 'nom', 'prenom', 'telephone']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations', {'fields': ('nom', 'prenom', 'telephone', 'type_compte')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
```

par :

```python
    list_display = ['email', 'nom', 'prenom', 'telephone', 'type_compte', 'statut_compte', 'is_active', 'date_joined']
    list_filter = ['type_compte', 'statut_compte', 'is_active', 'is_staff']
    search_fields = ['email', 'nom', 'prenom', 'telephone']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations', {'fields': ('nom', 'prenom', 'telephone', 'type_compte', 'statut_compte')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
```

- [ ] **Step 7: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (20 tests : les 19 existants + le nouveau).

- [ ] **Step 8: Commit**

```bash
cd vendor/core
git add -A src/app/models.py src/app/admin.py src/app/tests.py src/app/migrations/0002_utilisateur_statut_compte.py
git commit -m "feat(app): ajoute statut_compte sur Utilisateur (en_attente par défaut)"
```

---

## Task 2: Dashboard vendeur conditionné par `statut_compte`

**Files:**
- Modify: `vendor/core/src/app/views.py`
- Modify: `vendor/core/src/templates/app/layout/tableau_de_bord.html`
- Modify: `vendor/core/src/app/tests.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `vendor/core/src/app/tests.py`, remplacer la classe `TableauDeBordVendeurViewTest`
existante (elle contient actuellement `test_requires_login` et
`test_authenticated_user_sees_dashboard`) par :

```python
class TableauDeBordVendeurViewTest(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertRedirects(response, f"{reverse('connexion_vendeur')}?next={reverse('tableau_de_bord_vendeur')}")

    def test_compte_en_attente_montre_message_attente(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'en cours de validation')
        self.assertNotContains(response, 'Mes annonces')

    def test_compte_suspendu_montre_message_suspension(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        user.statut_compte = Utilisateur.StatutCompte.SUSPENDU
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'suspendu')
        self.assertNotContains(response, 'Mes annonces')

    def test_compte_actif_montre_dashboard_complet(self):
        user = Utilisateur.objects.create_user(
            email='ange@exemple.ci', password='MotDePasse1', nom='Koffi', prenom='Ange', telephone='0102030405',
        )
        user.statut_compte = Utilisateur.StatutCompte.ACTIF
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse('tableau_de_bord_vendeur'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bienvenue, Ange')
        self.assertContains(response, 'Mes annonces')
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd vendor/core/src && ../venv/Scripts/python.exe manage.py test app.tests.TableauDeBordVendeurViewTest -v 2`
Expected: `test_compte_en_attente_montre_message_attente` et
`test_compte_suspendu_montre_message_suspension` échouent (le template actuel affiche
toujours "Bienvenue, {prenom}" sans distinction de statut). `test_requires_login` passe
déjà.

- [ ] **Step 3: Passer le statut au contexte du template**

Dans `vendor/core/src/app/views.py`, `TableauDeBordVendeurView` est actuellement :

```python
class TableauDeBordVendeurView(LoginRequiredMixin, TemplateView):
    template_name = 'app/layout/tableau_de_bord.html'
    login_url = 'connexion_vendeur'
```

`request.user.statut_compte` est déjà accessible dans le template via `user` (context
processor `auth` déjà configuré) — aucun changement de vue n'est nécessaire, seul le
template change. Confirmer avec :

```bash
grep -n "django.contrib.auth.context_processors.auth" vendor/core/src/core/settings.py
```
Expected: une ligne la contenant (déjà présente depuis le scaffold initial).

- [ ] **Step 4: Réécrire le template avec le rendu conditionnel**

Remplacer tout le `{% block content %}` de
`vendor/core/src/templates/app/layout/tableau_de_bord.html` :

```html
{% block content %}
<div class="bg-background font-body-md text-on-surface min-h-screen flex flex-col">
    <header class="w-full border-b border-outline-variant/30 bg-surface">
        <div class="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <img alt="Djona" class="h-8 w-auto object-contain" src="{% static 'app/assets/img/djona-logo.png' %}">
                <span class="font-headline-md text-primary font-bold">Djona Vendeur</span>
            </div>
            <form action="{% url 'deconnexion_vendeur' %}" method="post">
                {% csrf_token %}
                <button class="text-sm font-semibold text-primary hover:underline" type="submit">Déconnexion</button>
            </form>
        </div>
    </header>

    <main class="flex-1 flex items-center justify-center px-6 py-16">
        {% if user.statut_compte == 'en_attente' %}
        <div class="max-w-md text-center flex flex-col items-center gap-4">
            <span class="material-symbols-outlined text-secondary text-[48px]">hourglass_top</span>
            <h1 class="font-headline-lg text-2xl text-primary">Bienvenue, {{ user.prenom }} !</h1>
            <p class="text-on-surface-variant">
                Votre compte est en cours de validation par notre équipe. Vous pourrez gérer vos
                annonces dès que votre compte aura été activé.
            </p>
        </div>
        {% elif user.statut_compte == 'suspendu' %}
        <div class="max-w-md text-center flex flex-col items-center gap-4">
            <span class="material-symbols-outlined text-error text-[48px]">block</span>
            <h1 class="font-headline-lg text-2xl text-primary">Compte suspendu</h1>
            <p class="text-on-surface-variant">
                Votre compte a été suspendu. Contactez notre support pour plus d'informations.
            </p>
        </div>
        {% else %}
        <div class="max-w-md text-center flex flex-col items-center gap-4">
            <span class="material-symbols-outlined text-primary text-[48px]">directions_car</span>
            <h1 class="font-headline-lg text-2xl text-primary">Bienvenue, {{ user.prenom }} !</h1>
            <p class="text-on-surface-variant">
                Votre compte {{ user.get_type_compte_display|lower }} est actif.
            </p>
            <a class="mt-2 px-6 py-3 bg-primary text-on-primary rounded-lg font-semibold hover:bg-primary/90 transition-colors" href="#">
                Mes annonces
            </a>
        </div>
        {% endif %}
    </main>
</div>
{% endblock %}
```

(Le lien « Mes annonces » pointe vers `href="#"` pour l'instant — il sera câblé sur la
vraie liste dans le prochain plan, quand l'app `annonces` existera côté vendor.)

Le fichier `{% block styles %}` (lignes 6-11 du template, tailwind config + fonts) ne
change pas.

- [ ] **Step 5: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test app.tests.TableauDeBordVendeurViewTest -v 2`
Expected: PASS (4 tests)

- [ ] **Step 6: Lancer toute la suite de tests du projet vendor**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (22 tests).

- [ ] **Step 7: Commit**

```bash
cd vendor/core
git add -A src/app/views.py src/templates/app/layout/tableau_de_bord.html src/app/tests.py
git commit -m "feat(app): dashboard vendeur conditionné par statut_compte"
```

---

## Task 3: Connexion `vendor_db` côté admin

**Files:**
- Modify: `admin/core/src/core/settings.py`
- Modify: `admin/core/.env`
- Modify: `admin/core/.env.example`
- Modify: `admin/core/requirements.txt` (déjà à jour — vérification seulement)

- [ ] **Step 1: Ajouter la variable au `.env` de admin**

Dans `admin/core/.env`, juste après la ligne `MYSQL_PORT=3307`, ajouter :

```
VENDOR_MYSQL_DB=djona_vendor
```

- [ ] **Step 2: Documenter la variable dans `.env.example`**

Dans `admin/core/.env.example`, ajouter la même ligne après `MYSQL_PORT` (valeur vide,
comme les autres exemples) :

```
VENDOR_MYSQL_DB=
```

- [ ] **Step 3: Ajouter la connexion `vendor_db` dans les settings**

Dans `admin/core/src/core/settings.py`, le bloc `DATABASES` actuel est :

```python
# Base de données — switcher via .env
if config('USE_MYSQL', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('MYSQL_DB'),
            'USER': config('MYSQL_USER'),
            'PASSWORD': config('MYSQL_PASSWORD'),
            'HOST': config('MYSQL_HOST', default='localhost'),
            'PORT': config('MYSQL_PORT', default='3306'),
            'OPTIONS': {'ssl': {'ssl-mode': 'REQUIRED'}},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

Remplacer par :

```python
# Base de données — switcher via .env
if config('USE_MYSQL', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('MYSQL_DB'),
            'USER': config('MYSQL_USER'),
            'PASSWORD': config('MYSQL_PASSWORD'),
            'HOST': config('MYSQL_HOST', default='localhost'),
            'PORT': config('MYSQL_PORT', default='3306'),
            'OPTIONS': {'ssl': {'ssl-mode': 'REQUIRED'}},
        },
        # Connexion en lecture/écriture vers le schéma du projet vendor (comptes
        # vendeur + annonces). Même serveur/utilisateur MySQL que `default`, seul le
        # nom de la base change. Utilisée uniquement par l'app `moderation`, via
        # `.using('vendor_db')` — jamais comme alias par défaut d'un modèle.
        'vendor_db': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('VENDOR_MYSQL_DB', default='djona_vendor'),
            'USER': config('MYSQL_USER'),
            'PASSWORD': config('MYSQL_PASSWORD'),
            'HOST': config('MYSQL_HOST', default='localhost'),
            'PORT': config('MYSQL_PORT', default='3306'),
            'OPTIONS': {'ssl': {'ssl-mode': 'REQUIRED'}},
            # ATTENTION : TEST.NAME pointe vers une base de test DÉDIÉE
            # (djona_vendor_test), PAS vers la vraie base djona_vendor. Le
            # test-runner Django exécute un DROP DATABASE + CREATE DATABASE sur
            # TEST.NAME à chaque `manage.py test` (sauf --keepdb) — pointer ça vers
            # la vraie base détruirait les données réelles du projet vendor.
            # djona_vendor_test est peuplée en rejouant les migrations du projet
            # vendor dessus (même utilisateur MySQL, mêmes identifiants, juste un
            # autre nom de base) ; à refaire si les modèles vendor changent de
            # schéma.
            'TEST': {'NAME': config('VENDOR_TEST_MYSQL_DB', default='djona_vendor_test')},
        },
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

- [ ] **Step 4: Vérifier que le projet démarre toujours correctement**

Run:
```bash
cd admin/core/src
../venv/Scripts/python.exe manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Vérifier la connectivité à `vendor_db` depuis le shell Django**

Run:
```bash
../venv/Scripts/python.exe manage.py shell -c "from django.db import connections; c = connections['vendor_db']; c.ensure_connection(); print('OK', c.settings_dict['NAME'])"
```
Expected: `OK djona_vendor`

- [ ] **Step 6: Lancer la suite de tests admin (aucune régression attendue)**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: les 29 tests existants passent toujours (aucun modèle n'utilise encore
`vendor_db`).

- [ ] **Step 7: Commit**

```bash
cd admin/core
git add -A .env.example src/core/settings.py
git commit -m "feat(core): ajoute la connexion base de données vendor_db"
```

(`admin/core/.env` n'est pas commité — il est dans `.gitignore`.)

---

## Task 4: App `moderation` — modèle miroir `CompteVendeur`

**Files:**
- Create: `admin/core/src/moderation/__init__.py`
- Create: `admin/core/src/moderation/apps.py`
- Create: `admin/core/src/moderation/models.py`
- Create: `admin/core/src/moderation/tests/__init__.py`
- Create: `admin/core/src/moderation/tests/test_models.py`
- Modify: `admin/core/src/core/settings.py` (`LOCAL_APPS`)

- [ ] **Step 1: Créer le squelette de l'app**

Run:
```bash
cd admin/core/src
../venv/Scripts/python.exe manage.py startapp moderation
```

Cela crée `admin/core/src/moderation/` avec `__init__.py`, `admin.py`, `apps.py`,
`migrations/`, `models.py`, `tests.py`, `views.py`. Supprimer `migrations/` (l'app n'a
que des modèles `managed=False`, aucune migration ne doit jamais être générée pour
elle) :

```bash
rm -rf moderation/migrations
rm moderation/tests.py
mkdir moderation/tests
touch moderation/tests/__init__.py
```

- [ ] **Step 2: Déclarer l'app dans les settings**

Dans `admin/core/src/core/settings.py`, `LOCAL_APPS` est actuellement :

```python
LOCAL_APPS = [
    'app',
    'annonces',
]
```

Remplacer par :

```python
LOCAL_APPS = [
    'app',
    'annonces',
    'moderation',
]
```

- [ ] **Step 3: Écrire le test qui échoue**

Dans `admin/core/src/moderation/tests/test_models.py` :

```python
from django.test import TestCase

from moderation.models import CompteVendeur


class CompteVendeurTest(TestCase):
    databases = {'vendor_db'}

    def test_lit_les_comptes_vendeur_reels(self):
        CompteVendeur.objects.using('vendor_db').create(
            email='test-moderation@exemple.ci',
            nom='Test',
            prenom='Moderation',
            telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE,
            is_active=True,
            date_joined='2026-08-27T10:00:00Z',
            password='inutilise',
        )
        compte = CompteVendeur.objects.using('vendor_db').get(email='test-moderation@exemple.ci')
        self.assertEqual(compte.prenom, 'Moderation')
        self.assertEqual(compte.statut_compte, CompteVendeur.StatutCompte.EN_ATTENTE)
```

`databases = {'vendor_db'}` est requis par Django : par défaut, `TestCase` bloque
l'accès à toute base autre que `default` pendant un test, pour éviter les fuites
accidentelles entre tests.

- [ ] **Step 4: Vérifier que le test échoue**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation -v 2`
Expected: `ModuleNotFoundError: No module named 'moderation.models'` (le fichier existe
mais est vide après `startapp`).

- [ ] **Step 5: Écrire le modèle miroir**

Contenu complet de `admin/core/src/moderation/models.py` :

```python
from django.db import models


class CompteVendeur(models.Model):
    """Miroir en lecture/écriture de vendor.app.Utilisateur (schéma djona_vendor,
    connexion 'vendor_db'). Ce modèle n'est jamais migré depuis ce projet — le
    schéma réel est possédé et migré par le projet vendor."""

    class TypeCompte(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        PROFESSIONNEL = 'professionnel', 'Professionnel'

    class StatutCompte(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'

    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices)
    statut_compte = models.CharField(max_length=20, choices=StatutCompte.choices)
    is_active = models.BooleanField()
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField()
    password = models.CharField(max_length=128)

    class Meta:
        managed = False
        db_table = 'vendeur_utilisateurs'

    def __str__(self):
        return f'{self.prenom} {self.nom} ({self.email})'
```

Le champ `password` est présent (colonne réelle de la table) mais n'est jamais utilisé
côté admin — nécessaire uniquement pour que `.create()`/`.save()` fonctionnent sans
erreur de colonne manquante lors des tests, la table réelle ayant `password NOT NULL`.
`is_staff`/`is_superuser` (ajoutés par `PermissionsMixin` sur le vrai modèle
`Utilisateur`) sont NOT NULL également côté base — nécessaires pour la même raison,
avec `default=False` pour que les tests n'aient pas à les préciser à chaque fois.

**Note settings.py :** l'entrée `vendor_db` (Task 3) doit aussi inclure
`'DEPENDENCIES': []` dans son dict `TEST`, sinon Django lève `Circular dependency in
TEST[DEPENDENCIES]` dès qu'un test cible `vendor_db` sans que `default` fasse partie
du même run (cas de `manage.py test moderation` isolé, par exemple) :
```python
'TEST': {'NAME': config('VENDOR_TEST_MYSQL_DB', default='djona_vendor_test'), 'DEPENDENCIES': []},
```

- [ ] **Step 6: Vérifier que le test passe**

Run: `../venv/Scripts/python.exe manage.py test moderation -v 2`
Expected: PASS

- [ ] **Step 7: Nettoyer la ligne de test insérée**

La table `vendeur_utilisateurs` réelle (schéma `djona_vendor`) a maintenant une ligne
de test résiduelle si le test a échoué en cours de route ou si `TestCase` n'a pas pu
faire son rollback (cas rare). Vérifier et nettoyer si besoin :

```bash
cd admin/core/src
../venv/Scripts/python.exe manage.py shell -c "
from moderation.models import CompteVendeur
n, _ = CompteVendeur.objects.using('vendor_db').filter(email='test-moderation@exemple.ci').delete()
print('supprimé:', n)
"
```
Expected: `supprimé: 0` (le rollback automatique de `TestCase` a déjà tout nettoyé — ce
step est une simple vérification de sécurité).

- [ ] **Step 8: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (30 tests : 29 existants + 1 nouveau).

- [ ] **Step 9: Commit**

```bash
cd admin/core
git add -A src/moderation src/core/settings.py
git commit -m "feat(moderation): ajoute le modèle miroir CompteVendeur"
```

---

## Task 5: Liste des vendeurs (admin)

**Files:**
- Create: `admin/core/src/moderation/views.py`
- Create: `admin/core/src/moderation/urls.py`
- Create: `admin/core/src/templates/moderation/vendeur_liste.html`
- Create: `admin/core/src/moderation/tests/test_views.py`
- Modify: `admin/core/src/core/urls.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Contenu complet de `admin/core/src/moderation/tests/test_views.py` :

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import CompteVendeur

User = get_user_model()


class VendeurListViewTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='motdepasse', is_staff=True)
        self.vendeur_attente = CompteVendeur.objects.using('vendor_db').create(
            email='attente@exemple.ci', nom='Koffi', prenom='Ange', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
            statut_compte=CompteVendeur.StatutCompte.EN_ATTENTE,
            is_active=True, date_joined='2026-08-27T10:00:00Z', password='inutilise',
        )
        self.vendeur_actif = CompteVendeur.objects.using('vendor_db').create(
            email='actif@exemple.ci', nom='Diallo', prenom='Fatou', telephone='0102030406',
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL,
            statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-26T10:00:00Z', password='inutilise',
        )

    def tearDown(self):
        CompteVendeur.objects.using('vendor_db').filter(
            email__in=['attente@exemple.ci', 'actif@exemple.ci'],
        ).delete()

    def test_requiert_authentification_staff(self):
        response = self.client.get(reverse('vendeur_liste'))
        self.assertRedirects(response, f"{reverse('connexion_admin')}?next={reverse('vendeur_liste')}")

    def test_liste_les_vendeurs_en_attente_en_premier(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vendeur_liste'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ange')
        self.assertContains(response, 'Fatou')
        content = response.content.decode()
        self.assertLess(content.index('Ange'), content.index('Fatou'))
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation.tests.test_views -v 2`
Expected: `NoReverseMatch: Reverse for 'vendeur_liste' not found`

- [ ] **Step 3: Écrire la vue**

Contenu complet de `admin/core/src/moderation/views.py` :

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.views.generic import ListView

from .models import CompteVendeur


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
```

- [ ] **Step 4: Écrire les URLs de l'app**

Contenu complet de `admin/core/src/moderation/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('vendeurs/', views.VendeurListView.as_view(), name='vendeur_liste'),
]
```

- [ ] **Step 5: Inclure les URLs de l'app dans le projet**

Dans `admin/core/src/core/urls.py`, remplacer :

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('annonces/', include('annonces.urls')),
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
    path('', include('moderation.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

- [ ] **Step 6: Écrire le template**

Contenu complet de `admin/core/src/templates/moderation/vendeur_liste.html` :

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Vendeurs — Portail Admin{% endblock %}

{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary":"#003b5a","primary-container":"#1a5276","secondary":"#865300","secondary-container":"#fea520","surface":"#f8f9f9","surface-container":"#edeeee","surface-container-lowest":"#ffffff","on-primary":"#ffffff","on-surface":"#191c1c","on-surface-variant":"#41474e","outline-variant":"#c1c7cf"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem"},"fontFamily":{"headline-md":["Montserrat"],"body-md":["Inter"],"label-md":["Inter"]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Montserrat:wght@600;700&amp;display=swap" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface min-h-screen lg:pl-72">
    <div class="max-w-6xl mx-auto px-container-margin-mobile lg:px-container-margin-desktop py-12">
        <h1 class="font-headline-md text-2xl text-primary mb-1">Vendeurs</h1>
        <p class="text-on-surface-variant mb-8">Comptes vendeur inscrits sur la plateforme.</p>

        <div class="bg-surface-container-lowest rounded-lg shadow-sm overflow-x-auto">
            <table class="w-full text-left text-sm">
                <thead class="bg-surface-container text-on-surface-variant uppercase text-xs">
                    <tr>
                        <th class="px-6 py-3">Nom</th>
                        <th class="px-6 py-3">Email</th>
                        <th class="px-6 py-3">Téléphone</th>
                        <th class="px-6 py-3">Type</th>
                        <th class="px-6 py-3">Inscription</th>
                        <th class="px-6 py-3">Statut</th>
                        <th class="px-6 py-3">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for vendeur in vendeurs %}
                    <tr class="border-t border-outline-variant/30">
                        <td class="px-6 py-4 font-semibold">{{ vendeur.prenom }} {{ vendeur.nom }}</td>
                        <td class="px-6 py-4 text-on-surface-variant">{{ vendeur.email }}</td>
                        <td class="px-6 py-4 text-on-surface-variant">{{ vendeur.telephone }}</td>
                        <td class="px-6 py-4">{{ vendeur.get_type_compte_display }}</td>
                        <td class="px-6 py-4 text-on-surface-variant">{{ vendeur.date_joined|date:'d/m/Y' }}</td>
                        <td class="px-6 py-4">
                            {% if vendeur.statut_compte == 'en_attente' %}
                            <span class="px-3 py-1 rounded-full bg-secondary-container/30 text-secondary text-xs font-bold">En attente</span>
                            {% elif vendeur.statut_compte == 'actif' %}
                            <span class="px-3 py-1 rounded-full bg-green-100 text-green-700 text-xs font-bold">Actif</span>
                            {% else %}
                            <span class="px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-bold">Suspendu</span>
                            {% endif %}
                        </td>
                        <td class="px-6 py-4">
                            {% if vendeur.statut_compte != 'actif' %}
                            <form action="{% url 'vendeur_activer' vendeur.pk %}" method="post" class="inline">
                                {% csrf_token %}
                                <button class="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-bold hover:bg-primary/90 transition-colors" type="submit">Activer</button>
                            </form>
                            {% else %}
                            <form action="{% url 'vendeur_suspendre' vendeur.pk %}" method="post" class="inline">
                                {% csrf_token %}
                                <button class="px-3 py-1.5 rounded-lg border border-red-300 text-red-700 text-xs font-bold hover:bg-red-50 transition-colors" type="submit">Suspendre</button>
                            </form>
                            {% endif %}
                        </td>
                    </tr>
                    {% empty %}
                    <tr><td class="px-6 py-8 text-center text-on-surface-variant" colspan="7">Aucun vendeur inscrit pour le moment.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test moderation.tests.test_views -v 2`
Expected: PASS (2 tests)

- [ ] **Step 8: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (32 tests).

- [ ] **Step 9: Commit**

```bash
cd admin/core
git add -A src/moderation src/templates/moderation src/core/urls.py
git commit -m "feat(moderation): ajoute la liste des vendeurs"
```

---

## Task 6: Actions Activer / Suspendre

**Files:**
- Modify: `admin/core/src/moderation/views.py`
- Modify: `admin/core/src/moderation/urls.py`
- Modify: `admin/core/src/moderation/tests/test_views.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter ces deux méthodes à `VendeurListViewTest` dans
`admin/core/src/moderation/tests/test_views.py` (après
`test_liste_les_vendeurs_en_attente_en_premier`) :

```python
    def test_activer_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('vendeur_activer', args=[self.vendeur_attente.pk]))
        self.assertRedirects(response, reverse('vendeur_liste'))
        self.vendeur_attente.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur_attente.statut_compte, CompteVendeur.StatutCompte.ACTIF)

    def test_suspendre_change_le_statut(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('vendeur_suspendre', args=[self.vendeur_actif.pk]))
        self.assertRedirects(response, reverse('vendeur_liste'))
        self.vendeur_actif.refresh_from_db(using='vendor_db')
        self.assertEqual(self.vendeur_actif.statut_compte, CompteVendeur.StatutCompte.SUSPENDU)

    def test_activer_refuse_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vendeur_activer', args=[self.vendeur_attente.pk]))
        self.assertEqual(response.status_code, 405)
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test moderation.tests.test_views -v 2`
Expected: `NoReverseMatch: Reverse for 'vendeur_activer' not found`

- [ ] **Step 3: Ajouter les vues d'action**

Remplacer tout le contenu de `admin/core/src/moderation/views.py` (imports en tête de
fichier mis à jour avec les 4 nouveaux + classes `_VendeurActionView`,
`VendeurActiverView`, `VendeurSuspendreView` ajoutées après `VendeurListView`) :

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import CompteVendeur


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
```

`require_POST` renvoie une réponse HTTP 405 pour toute méthode autre que POST (couvre
`test_activer_refuse_get`) — pas besoin de la gérer manuellement.

- [ ] **Step 4: Ajouter les routes**

Contenu complet de `admin/core/src/moderation/urls.py` :

```python
from django.urls import path

from . import views

urlpatterns = [
    path('vendeurs/', views.VendeurListView.as_view(), name='vendeur_liste'),
    path('vendeurs/<int:pk>/activer/', views.VendeurActiverView.as_view(), name='vendeur_activer'),
    path('vendeurs/<int:pk>/suspendre/', views.VendeurSuspendreView.as_view(), name='vendeur_suspendre'),
]
```

- [ ] **Step 5: Vérifier que les tests passent**

Run: `../venv/Scripts/python.exe manage.py test moderation.tests.test_views -v 2`
Expected: PASS (5 tests)

- [ ] **Step 6: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (35 tests).

- [ ] **Step 7: Commit**

```bash
cd admin/core
git add -A src/moderation
git commit -m "feat(moderation): ajoute les actions activer/suspendre un vendeur"
```

---

## Task 7: Lien de navigation « Vendeurs » dans le dashboard admin

**Files:**
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

Le dashboard admin a déjà un lien de navigation « Users » (desktop ET mobile) qui
pointait vers `href="#"` (jamais câblé). On le renomme et on le câble vers la nouvelle
liste des vendeurs plutôt que d'ajouter un nouveau lien redondant.

- [ ] **Step 1: Câbler le lien desktop**

Dans `admin/core/src/templates/app/layout/dashboard_admin.html`, la sidebar desktop
contient actuellement (vers la ligne 48) :

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Users</span>
</a>
```

Remplacer par :

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Vendeurs</span>
</a>
```

- [ ] **Step 2: Câbler le lien mobile**

Plus bas dans le même fichier, la nav mobile basse contient (vers la ligne 348) :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="#">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Users</span>
</a>
```

Remplacer par :

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Vendeurs</span>
</a>
```

- [ ] **Step 3: Vérifier que le dashboard se charge sans erreur**

Run:
```bash
cd admin/core/src
../venv/Scripts/python.exe manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Lancer toute la suite de tests admin**

Run: `../venv/Scripts/python.exe manage.py test`
Expected: tous les tests passent (35 tests — ce template n'a pas de test dédié, la
vérification est visuelle à l'étape suivante).

- [ ] **Step 5: Vérification manuelle bout en bout**

Démarrer les deux serveurs (deux terminaux) :
```bash
cd vendor/core/src && ../venv/Scripts/python.exe manage.py runserver 8010
cd admin/core/src && ../venv/Scripts/python.exe manage.py runserver 8020
```

1. Ouvrir `http://127.0.0.1:8010/inscription/`, créer un compte vendeur test.
2. Vérifier que le dashboard vendeur affiche le message « en cours de validation ».
3. Ouvrir `http://127.0.0.1:8020/connexion/`, se connecter avec le compte superadmin
   existant (`admin@gmail.com`).
4. Cliquer sur « Vendeurs » dans la sidebar — le vendeur test créé à l'étape 1 doit
   apparaître avec le statut « En attente ».
5. Cliquer sur « Activer ».
6. Retourner sur le dashboard vendeur (`http://127.0.0.1:8010/tableau-de-bord/`,
   rafraîchir) — le message doit maintenant être « Votre compte ... est actif » avec le
   lien « Mes annonces ».

Arrêter les deux serveurs une fois la vérification faite.

- [ ] **Step 6: Commit**

```bash
cd admin/core
git add -A src/templates/app/layout/dashboard_admin.html
git commit -m "feat(dashboard): câble le lien de navigation Vendeurs"
```

---

## Récapitulatif

À la fin de ce plan :
- Un vendeur qui s'inscrit démarre `en_attente`, peut se connecter, voit un dashboard
  limité.
- L'admin voit tous les comptes vendeur (via `vendor_db`) et peut les activer/suspendre.
- Le vendeur activé voit un dashboard complet (le lien « Mes annonces » reste `href="#"`
  — câblé dans le plan suivant : `docs/superpowers/plans/2026-08-27-gestion-validation-annonces.md`).

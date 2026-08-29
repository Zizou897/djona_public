# Page "Gestion du Profil" (backoffice admin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a working `/profil/` page to the `admin` Django project (`admin/core/src`) where the connected staff user can view/edit personal info, change password, toggle a 2FA preference, and set notification/language preferences — reproducing the visual design of `admin/_utilisateur/desktop/param_tres_du_profil_djona/screen.png` but wired to the real staff account and shell already used by `/tableau-de-bord/`.

**Architecture:** New `Profil` model (1-1 with `User`) holds fields `User` doesn't have (phone, city, avatar, 2FA preference, language, notification channels). Two views (`ProfilView` for the main form, `ProfilPasswordChangeView` for password change) reuse a new `StaffRequisMixin` extracted from the existing `AdminDashboardView`. The shared sidebar/mobile-nav markup duplicated across admin pages is extracted into `templates/app/includes/`, then both `dashboard_admin.html` and the new `profil_admin.html` use it.

**Tech Stack:** Django 5 (`admin/core`), SQLite (dev), Tailwind via CDN (per-page config script), vanilla JS (no framework), Pillow (already in `requirements.txt`, needed for `ImageField`).

**Spec:** `docs/superpowers/specs/2026-08-28-profil-admin-design.md`

---

All commands below run from the repo root and use the project's existing venv
(`admin/core/venv`). All `manage.py` commands run with:

```bash
cd admin/core/src && ../venv/Scripts/python.exe manage.py <command>
```

**Test database note:** `admin/core/.env` points `manage.py test` at a real local MySQL
server (`127.0.0.1:3307`, schema `djona_admin`) shared with the main checkout — it is
untracked (gitignored) and was copied in when this worktree was set up. A previous run
already left a `test_djona_admin` database behind, so running `manage.py test` without
`--keepdb` prompts interactively to drop it and hangs/fails non-interactively. **Always
pass `--keepdb`** on every `manage.py test` invocation in this plan (already reflected in
the commands below).

## Task 1: `Profil` model + admin registration

**Files:**
- Modify: `admin/core/src/app/models.py`
- Modify: `admin/core/src/app/admin.py`
- Create: `admin/core/src/app/tests_profil.py`
- Create (generated): `admin/core/src/app/migrations/__init__.py`, `admin/core/src/app/migrations/0001_initial.py`

- [ ] **Step 1: Write the failing model test**

Create `admin/core/src/app/tests_profil.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Profil

User = get_user_model()


class ProfilModelTest(TestCase):
    def test_default_values(self):
        user = User.objects.create_user(username='staff-modele', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        self.assertEqual(profil.ville, '')
        self.assertEqual(profil.telephone, '')
        self.assertFalse(profil.avatar)
        self.assertFalse(profil.two_factor_enabled)
        self.assertEqual(profil.langue, Profil.Langue.FRANCAIS)
        self.assertTrue(profil.notif_email)
        self.assertTrue(profil.notif_whatsapp)

    def test_str(self):
        user = User.objects.create_user(username='staff-str', password='motdepasse123')
        profil = Profil.objects.create(user=user)
        self.assertEqual(str(profil), 'Profil de staff-str')
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil -v 2`
Expected: `ImportError: cannot import name 'Profil' from 'app.models'` (or `ModuleNotFoundError`).

- [ ] **Step 3: Add the `Profil` model**

In `admin/core/src/app/models.py`, add `from django.conf import settings` to the top import and append the model after `Convention`:

```python
from django.conf import settings
from django.db import models

class Convention(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Profil(models.Model):
    class Ville(models.TextChoices):
        ABIDJAN_COCODY = 'abidjan_cocody', 'Abidjan, Cocody'
        ABIDJAN_MARCORY = 'abidjan_marcory', 'Abidjan, Marcory'
        ABIDJAN_KOUMASSI = 'abidjan_koumassi', 'Abidjan, Koumassi'
        YAMOUSSOUKRO = 'yamoussoukro', 'Yamoussoukro'
        BOUAKE = 'bouake', 'Bouaké'

    class Langue(models.TextChoices):
        FRANCAIS = 'fr', 'Français'
        ANGLAIS = 'en', 'English'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil',
    )
    telephone = models.CharField(max_length=30, blank=True)
    ville = models.CharField(max_length=30, choices=Ville.choices, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False)
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FRANCAIS)
    notif_email = models.BooleanField(default=True)
    notif_whatsapp = models.BooleanField(default=True)

    def __str__(self):
        return f'Profil de {self.user}'
```

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
cd admin/core/src && ../venv/Scripts/python.exe manage.py makemigrations app
```
Expected: `Migrations for 'app': app/migrations/0001_initial.py - Create model Profil`

Run:
```bash
cd admin/core/src && ../venv/Scripts/python.exe manage.py migrate app
```
Expected: `Applying app.0001_initial... OK`

- [ ] **Step 5: Register `Profil` in the Django admin**

Replace `admin/core/src/app/admin.py`:

```python
from django.contrib import admin

from .models import Profil


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'telephone', 'ville', 'two_factor_enabled')
    search_fields = ('user__username', 'user__email', 'telephone')
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil -v 2`
Expected: `OK` (2 tests)

- [ ] **Step 7: Commit**

```bash
git add admin/core/src/app/models.py admin/core/src/app/admin.py admin/core/src/app/tests_profil.py admin/core/src/app/migrations
git commit -m "feat(admin): ajoute le modèle Profil (téléphone, ville, avatar, 2FA, préférences)"
```

---

## Task 2: Extract `StaffRequisMixin` (no behavior change)

`AdminDashboardView` currently duplicates the `LoginRequiredMixin` + `UserPassesTestMixin(is_staff)` +
`handle_no_permission` guard inline. Task 4 adds two more views needing the exact same guard —
extract it now so it's written once.

**Files:**
- Modify: `admin/core/src/app/views.py`

- [ ] **Step 1: Confirm the existing dashboard test currently passes (baseline)**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (3 tests, from `AdminDashboardViewAccessTest`)

- [ ] **Step 2: Extract the mixin**

In `admin/core/src/app/views.py`, replace:

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, redirect_to_login
from django.shortcuts import render
from django.views.generic import TemplateView


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

with:

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, redirect_to_login
from django.shortcuts import render
from django.views.generic import TemplateView


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
```

- [ ] **Step 3: Run the dashboard test again to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (3 tests, same as baseline)

- [ ] **Step 4: Commit**

```bash
git add admin/core/src/app/views.py
git commit -m "refactor(admin): extrait StaffRequisMixin de AdminDashboardView"
```

---

## Task 3: Forms

**Files:**
- Create: `admin/core/src/app/forms.py`
- Create: `admin/core/src/app/tests_forms.py`

- [ ] **Step 1: Write the failing form tests**

Create `admin/core/src/app/tests_forms.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from app.forms import ProfilForm, UtilisateurInfoForm
from app.models import Profil

User = get_user_model()


class UtilisateurInfoFormTest(TestCase):
    def test_save_splits_full_name_on_first_space(self):
        user = User.objects.create_user(username='staff-info', password='motdepasse123')
        form = UtilisateurInfoForm(data={'nom_complet': 'Koffi Konan', 'email': 'koffi@example.com'})
        self.assertTrue(form.is_valid(), form.errors)

        form.save(user)
        user.refresh_from_db()

        self.assertEqual(user.first_name, 'Koffi')
        self.assertEqual(user.last_name, 'Konan')
        self.assertEqual(user.email, 'koffi@example.com')

    def test_invalid_without_email(self):
        form = UtilisateurInfoForm(data={'nom_complet': 'Koffi Konan', 'email': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class ProfilFormTest(TestCase):
    def test_valid_data_saves(self):
        user = User.objects.create_user(username='staff-profilform', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        form = ProfilForm(data={
            'telephone': '+225 07 00 00 00 00',
            'ville': Profil.Ville.ABIDJAN_COCODY,
            'two_factor_enabled': 'on',
            'langue': Profil.Langue.FRANCAIS,
            'notif_email': 'on',
        }, instance=profil)
        self.assertTrue(form.is_valid(), form.errors)

        form.save()
        profil.refresh_from_db()

        self.assertEqual(profil.telephone, '+225 07 00 00 00 00')
        self.assertEqual(profil.ville, Profil.Ville.ABIDJAN_COCODY)
        self.assertTrue(profil.two_factor_enabled)
        self.assertTrue(profil.notif_email)
        self.assertFalse(profil.notif_whatsapp)

    def test_optional_fields_can_be_blank(self):
        user = User.objects.create_user(username='staff-profilform2', password='motdepasse123')
        profil = Profil.objects.create(user=user)

        form = ProfilForm(data={}, instance=profil)
        self.assertTrue(form.is_valid(), form.errors)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_forms -v 2`
Expected: `ModuleNotFoundError: No module named 'app.forms'`

- [ ] **Step 3: Write the forms**

Create `admin/core/src/app/forms.py`:

```python
from django import forms

from .models import Profil


class UtilisateurInfoForm(forms.Form):
    nom_complet = forms.CharField(max_length=150, label='Nom complet')
    email = forms.EmailField(label='Email')

    def save(self, user):
        nom_complet = self.cleaned_data['nom_complet'].strip()
        prenom, _, nom = nom_complet.partition(' ')
        user.first_name = prenom
        user.last_name = nom
        user.email = self.cleaned_data['email']
        user.save(update_fields=['first_name', 'last_name', 'email'])


class ProfilForm(forms.ModelForm):
    class Meta:
        model = Profil
        fields = [
            'telephone', 'ville', 'avatar',
            'two_factor_enabled', 'langue', 'notif_email', 'notif_whatsapp',
        ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_forms -v 2`
Expected: `OK` (3 tests)

- [ ] **Step 5: Commit**

```bash
git add admin/core/src/app/forms.py admin/core/src/app/tests_forms.py
git commit -m "feat(admin): formulaires UtilisateurInfoForm et ProfilForm"
```

---

## Task 4: `ProfilView` + `ProfilPasswordChangeView` + URLs + minimal template

Builds the working views first with a minimal stub template (no `TemplateDoesNotExist`
failures), so the HTTP-level behavior (auth guard, `Profil` auto-creation, save logic,
password change) is fully tested before the real UI is built in Task 6.

**Files:**
- Modify: `admin/core/src/app/views.py`
- Modify: `admin/core/src/app/urls.py`
- Create: `admin/core/src/templates/app/layout/profil_admin.html` (stub, replaced in Task 6)
- Create: `admin/core/src/app/tests_profil_view.py`

- [ ] **Step 1: Write the failing view tests**

Create `admin/core/src/app/tests_profil_view.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models import Profil

User = get_user_model()


class ProfilViewAccessTest(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('profil_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('profil_admin')}")

    def test_non_staff_is_redirected_to_login(self):
        User.objects.create_user(username='client-profil', password='motdepasse123', is_staff=False)
        self.client.login(username='client-profil', password='motdepasse123')
        response = self.client.get(reverse('profil_admin'))
        self.assertRedirects(response, f"/connexion/?next={reverse('profil_admin')}")

    def test_staff_can_view_profil_and_profil_is_created(self):
        user = User.objects.create_user(username='staff-view', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-view', password='motdepasse123')

        self.assertFalse(Profil.objects.filter(user=user).exists())
        response = self.client.get(reverse('profil_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profil.objects.filter(user=user).exists())


class ProfilViewUpdateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff-update', password='motdepasse123', is_staff=True,
            first_name='Ancien', last_name='Nom', email='ancien@example.com',
        )
        self.client.login(username='staff-update', password='motdepasse123')

    def test_post_updates_user_and_profil(self):
        response = self.client.post(reverse('profil_admin'), {
            'nom_complet': 'Koffi Konan',
            'email': 'koffi.konan@example.com',
            'telephone': '+225 07 00 00 00 00',
            'ville': Profil.Ville.ABIDJAN_COCODY,
            'two_factor_enabled': 'on',
            'langue': Profil.Langue.FRANCAIS,
            'notif_email': 'on',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Koffi')
        self.assertEqual(self.user.last_name, 'Konan')
        self.assertEqual(self.user.email, 'koffi.konan@example.com')

        profil = Profil.objects.get(user=self.user)
        self.assertEqual(profil.telephone, '+225 07 00 00 00 00')
        self.assertTrue(profil.two_factor_enabled)
        self.assertTrue(profil.notif_email)
        self.assertFalse(profil.notif_whatsapp)

    def test_post_with_invalid_email_does_not_save(self):
        response = self.client.post(reverse('profil_admin'), {
            'nom_complet': 'Koffi Konan',
            'email': 'pas-un-email',
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ancien@example.com')


class ProfilPasswordChangeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staff-pwd', password='ancienmdp123', is_staff=True)
        self.client.login(username='staff-pwd', password='ancienmdp123')

    def test_wrong_old_password_does_not_change_password(self):
        response = self.client.post(reverse('profil_mot_de_passe'), {
            'old_password': 'mauvais',
            'new_password1': 'nouveaumdp456',
            'new_password2': 'nouveaumdp456',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ancienmdp123'))

    def test_valid_password_change_keeps_session(self):
        response = self.client.post(reverse('profil_mot_de_passe'), {
            'old_password': 'ancienmdp123',
            'new_password1': 'nouveaumdp456',
            'new_password2': 'nouveaumdp456',
        })

        self.assertRedirects(response, reverse('profil_admin'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('nouveaumdp456'))

        # update_session_auth_hash a bien été appelé : la session reste valide,
        # la page suivante ne redemande pas de connexion.
        response2 = self.client.get(reverse('profil_admin'))
        self.assertEqual(response2.status_code, 200)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil_view -v 2`
Expected: `NoReverseMatch: Reverse for 'profil_admin' not found`

- [ ] **Step 3: Add the minimal stub template**

Create `admin/core/src/templates/app/layout/profil_admin.html`:

```html
{% extends 'app/base/base.html' %}

{% block title %}Profil — Portail Admin{% endblock %}

{% block content %}
<p>Profil</p>
{% endblock %}
```

- [ ] **Step 4: Add the views**

In `admin/core/src/app/views.py`, add these imports at the top (alongside the existing
ones) and the two new view classes at the end of the file:

```python
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect
from django.views import View

from .forms import ProfilForm, UtilisateurInfoForm
from .models import Profil
```

```python
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
```

Note: `render` is already imported at the top of `views.py` (used by `home`) — no new
import needed for it.

- [ ] **Step 5: Add the URLs**

In `admin/core/src/app/urls.py`, replace:

```python
urlpatterns = [
    path('', views.home, name='home'),
    path('connexion/', views.AdminLoginView.as_view(), name='connexion_admin'),
    path('deconnexion/', LogoutView.as_view(), name='deconnexion_admin'),
    path('tableau-de-bord/', views.AdminDashboardView.as_view(), name='dashboard_admin'),
]
```

with:

```python
urlpatterns = [
    path('', views.home, name='home'),
    path('connexion/', views.AdminLoginView.as_view(), name='connexion_admin'),
    path('deconnexion/', LogoutView.as_view(), name='deconnexion_admin'),
    path('tableau-de-bord/', views.AdminDashboardView.as_view(), name='dashboard_admin'),
    path('profil/', views.ProfilView.as_view(), name='profil_admin'),
    path('profil/mot-de-passe/', views.ProfilPasswordChangeView.as_view(), name='profil_mot_de_passe'),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil_view -v 2`
Expected: `OK` (7 tests)

- [ ] **Step 7: Run the full app test suite to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app -v 2`
Expected: `OK` (all tests across `tests.py`, `tests_profil.py`, `tests_forms.py`, `tests_profil_view.py`)

- [ ] **Step 8: Commit**

```bash
git add admin/core/src/app/views.py admin/core/src/app/urls.py admin/core/src/app/tests_profil_view.py admin/core/src/templates/app/layout/profil_admin.html
git commit -m "feat(admin): vues ProfilView et ProfilPasswordChangeView + routes /profil/"
```

---

## Task 5: Extract shared sidebar/mobile-nav/styles includes

`dashboard_admin.html` currently has the sidebar, mobile bottom nav, and Tailwind config
script inline. `profil_admin.html` (Task 6) needs the exact same shell, so extract these
into includes now instead of duplicating ~100 lines a second time.

**Files:**
- Create: `admin/core/src/templates/app/includes/styles_admin.html`
- Create: `admin/core/src/templates/app/includes/sidebar_admin.html`
- Create: `admin/core/src/templates/app/includes/nav_mobile_admin.html`
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Confirm the baseline dashboard test still passes**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (3 tests)

- [ ] **Step 2: Extract the styles include**

Create `admin/core/src/templates/app/includes/styles_admin.html` with this exact content
(copied verbatim from `dashboard_admin.html`'s current `{% block styles %}`):

```html
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary-fixed":"#cbe6ff","on-primary-fixed-variant":"#0e4b6e","surface-container-lowest":"#ffffff","on-primary-container":"#94c5ee","outline-variant":"#c1c7cf","primary":"#003b5a","on-tertiary-container":"#aec1d8","inverse-on-surface":"#f0f1f1","on-secondary-fixed-variant":"#663e00","surface":"#f8f9f9","secondary-container":"#fea520","surface-container-high":"#e7e8e8","background":"#f8f9f9","surface-dim":"#d9dada","on-secondary":"#ffffff","inverse-primary":"#9bccf6","on-error-container":"#93000a","on-primary-fixed":"#001e30","on-secondary-container":"#694000","on-tertiary":"#ffffff","tertiary":"#26384b","secondary-fixed":"#ffddb9","tertiary-container":"#3d4f63","surface-variant":"#e1e3e3","surface-container-highest":"#e1e3e3","secondary-fixed-dim":"#ffb961","surface-container":"#edeeee","inverse-surface":"#2e3131","primary-fixed-dim":"#9bccf6","surface-container-low":"#f3f4f4","surface-bright":"#f8f9f9","on-error":"#ffffff","on-background":"#191c1c","tertiary-fixed":"#d1e4fc","outline":"#72787f","error-container":"#ffdad6","on-surface":"#191c1c","on-surface-variant":"#41474e","on-secondary-fixed":"#2b1700","error":"#ba1a1a","surface-tint":"#2f6388","primary-container":"#1a5276","on-tertiary-fixed":"#091d2e","tertiary-fixed-dim":"#b5c8e0","on-primary":"#ffffff","secondary":"#865300","on-tertiary-fixed-variant":"#36485c"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem","xl":"0.75rem","full":"9999px"},"spacing":{"container-margin-desktop":"32px","section-gap":"48px","container-margin-mobile":"16px","base":"8px","gutter":"16px"},"fontFamily":{"label-sm":["Inter"],"headline-lg-mobile":["Montserrat"],"display-lg":["Montserrat"],"headline-lg":["Montserrat"],"body-lg":["Inter"],"body-md":["Inter"],"headline-md":["Montserrat"],"label-md":["Inter"]},"fontSize":{"label-sm":["10px",{"lineHeight":"14px","fontWeight":"500"}],"headline-lg-mobile":["18px",{"lineHeight":"24px","fontWeight":"700"}],"display-lg":["26px",{"lineHeight":"32px","letterSpacing":"-0.02em","fontWeight":"700"}],"headline-lg":["22px",{"lineHeight":"28px","fontWeight":"700"}],"body-lg":["14px",{"lineHeight":"20px","fontWeight":"400"}],"body-md":["13px",{"lineHeight":"18px","fontWeight":"400"}],"headline-md":["15px",{"lineHeight":"20px","fontWeight":"600"}],"label-md":["11px",{"lineHeight":"16px","letterSpacing":"0.01em","fontWeight":"600"}]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100..900&amp;family=Montserrat:wght@100..900&amp;display=swap" rel="stylesheet">
```

- [ ] **Step 3: Extract the sidebar include**

Create `admin/core/src/templates/app/includes/sidebar_admin.html`:

```html
{% load static %}
<aside class="hidden lg:flex fixed left-0 top-0 h-full w-72 bg-primary text-on-primary z-50 flex-col shadow-xl">
<div class="p-gutter flex items-center gap-3 mb-section-gap">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<span class="font-headline-md text-headline-md tracking-tight">Djona Admin</span>
</div>
<nav class="flex-1 px-4 flex flex-col gap-base">
<a {% if active_nav == 'dashboard' %}aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm"{% else %}class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all"{% endif %} href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined mr-4">dashboard</span><span class="font-label-md text-label-md">Dashboard</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Annonces à valider</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Vendeurs</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="#">
<span class="material-symbols-outlined mr-4">receipt_long</span><span class="font-label-md text-label-md">Transactions</span>
</a>
<div class="mt-auto mb-4 border-t border-on-primary/10 pt-4">
<a {% if active_nav == 'profil' %}aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm"{% else %}class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all"{% endif %} href="{% url 'profil_admin' %}">
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
```

- [ ] **Step 4: Extract the mobile bottom nav include**

Create `admin/core/src/templates/app/includes/nav_mobile_admin.html`:

```html
<nav class="lg:hidden fixed bottom-0 inset-x-0 z-50 bg-surface/80 backdrop-blur-xl shadow-[0_-1px_8px_rgba(0,0,0,0.04)] pb-safe">
<div class="flex justify-around items-center h-16 px-container-margin-mobile">
<a {% if active_nav == 'dashboard' %}aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary"{% else %}class="flex flex-col items-center justify-center gap-1 text-on-surface-variant"{% endif %} href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined">dashboard</span><span class="font-label-sm text-label-sm">Dashboard</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Vendeurs</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="#">
<span class="material-symbols-outlined">receipt_long</span><span class="font-label-sm text-label-sm">Transactions</span>
</a>
<a {% if active_nav == 'profil' %}aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary"{% else %}class="flex flex-col items-center justify-center gap-1 text-on-surface-variant"{% endif %} href="{% url 'profil_admin' %}">
<span class="material-symbols-outlined">settings</span><span class="font-label-sm text-label-sm">Réglages</span>
</a>
</div>
</nav>
```

- [ ] **Step 5: Wire the includes into `dashboard_admin.html`**

Replace the `{% block styles %}` block:

```html
{% block styles %}
<script src="https://cdn.tailwindcss.com"></script>
<script id="tailwind-config">tailwind.config={theme:{extend:{"colors":{"primary-fixed":"#cbe6ff","on-primary-fixed-variant":"#0e4b6e","surface-container-lowest":"#ffffff","on-primary-container":"#94c5ee","outline-variant":"#c1c7cf","primary":"#003b5a","on-tertiary-container":"#aec1d8","inverse-on-surface":"#f0f1f1","on-secondary-fixed-variant":"#663e00","surface":"#f8f9f9","secondary-container":"#fea520","surface-container-high":"#e7e8e8","background":"#f8f9f9","surface-dim":"#d9dada","on-secondary":"#ffffff","inverse-primary":"#9bccf6","on-error-container":"#93000a","on-primary-fixed":"#001e30","on-secondary-container":"#694000","on-tertiary":"#ffffff","tertiary":"#26384b","secondary-fixed":"#ffddb9","tertiary-container":"#3d4f63","surface-variant":"#e1e3e3","surface-container-highest":"#e1e3e3","secondary-fixed-dim":"#ffb961","surface-container":"#edeeee","inverse-surface":"#2e3131","primary-fixed-dim":"#9bccf6","surface-container-low":"#f3f4f4","surface-bright":"#f8f9f9","on-error":"#ffffff","on-background":"#191c1c","tertiary-fixed":"#d1e4fc","outline":"#72787f","error-container":"#ffdad6","on-surface":"#191c1c","on-surface-variant":"#41474e","on-secondary-fixed":"#2b1700","error":"#ba1a1a","surface-tint":"#2f6388","primary-container":"#1a5276","on-tertiary-fixed":"#091d2e","tertiary-fixed-dim":"#b5c8e0","on-primary":"#ffffff","secondary":"#865300","on-tertiary-fixed-variant":"#36485c"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem","xl":"0.75rem","full":"9999px"},"spacing":{"container-margin-desktop":"32px","section-gap":"48px","container-margin-mobile":"16px","base":"8px","gutter":"16px"},"fontFamily":{"label-sm":["Inter"],"headline-lg-mobile":["Montserrat"],"display-lg":["Montserrat"],"headline-lg":["Montserrat"],"body-lg":["Inter"],"body-md":["Inter"],"headline-md":["Montserrat"],"label-md":["Inter"]},"fontSize":{"label-sm":["10px",{"lineHeight":"14px","fontWeight":"500"}],"headline-lg-mobile":["18px",{"lineHeight":"24px","fontWeight":"700"}],"display-lg":["26px",{"lineHeight":"32px","letterSpacing":"-0.02em","fontWeight":"700"}],"headline-lg":["22px",{"lineHeight":"28px","fontWeight":"700"}],"body-lg":["14px",{"lineHeight":"20px","fontWeight":"400"}],"body-md":["13px",{"lineHeight":"18px","fontWeight":"400"}],"headline-md":["15px",{"lineHeight":"20px","fontWeight":"600"}],"label-md":["11px",{"lineHeight":"16px","letterSpacing":"0.01em","fontWeight":"600"}]}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100..900&amp;family=Montserrat:wght@100..900&amp;display=swap" rel="stylesheet">
{% endblock %}
```

with:

```html
{% block styles %}
{% include 'app/includes/styles_admin.html' %}
{% endblock %}
```

Replace the `<aside>...</aside>` block (the whole desktop sidebar, right after the mobile
`<header>` closes):

```html
<aside class="hidden lg:flex fixed left-0 top-0 h-full w-72 bg-primary text-on-primary z-50 flex-col shadow-xl">
<div class="p-gutter flex items-center gap-3 mb-section-gap">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<span class="font-headline-md text-headline-md tracking-tight">Djona Admin</span>
</div>
<nav class="flex-1 px-4 flex flex-col gap-base">
<a aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined mr-4">dashboard</span><span class="font-label-md text-label-md">Dashboard</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Annonces à valider</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Vendeurs</span>
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
```

with:

```html
{% include 'app/includes/sidebar_admin.html' with active_nav='dashboard' %}
```

Replace the mobile bottom nav block at the end of the file:

```html
<!-- Navigation basse mobile/tablette (< lg) -->
<nav class="lg:hidden fixed bottom-0 inset-x-0 z-50 bg-surface/80 backdrop-blur-xl shadow-[0_-1px_8px_rgba(0,0,0,0.04)] pb-safe">
<div class="flex justify-around items-center h-16 px-container-margin-mobile">
<a aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary" href="{% url 'dashboard_admin' %}">
<span class="material-symbols-outlined">dashboard</span><span class="font-label-sm text-label-sm">Dashboard</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Vendeurs</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="#">
<span class="material-symbols-outlined">receipt_long</span><span class="font-label-sm text-label-sm">Transactions</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'admin:index' %}">
<span class="material-symbols-outlined">settings</span><span class="font-label-sm text-label-sm">Réglages</span>
</a>
</div>
</nav>
```

with:

```html
{% include 'app/includes/nav_mobile_admin.html' with active_nav='dashboard' %}
```

- [ ] **Step 6: Run the dashboard test to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (3 tests) — a broken include (typo, missing `{% load static %}`, wrong url
name) would raise `TemplateSyntaxError`/`NoReverseMatch` and turn `test_staff_can_view_dashboard`'s
`assertEqual(response.status_code, 200)` into a failure, so this is a real regression check.

- [ ] **Step 7: Commit**

```bash
git add admin/core/src/templates/app/includes admin/core/src/templates/app/layout/dashboard_admin.html
git commit -m "refactor(admin): extrait sidebar/nav mobile/styles en includes partagés"
```

---

## Task 6: Full `profil_admin.html` UI

Replaces the Task 4 stub with the real page, matching
`admin/_utilisateur/desktop/param_tres_du_profil_djona/screen.png` adapted per the design
doc (staff shell, role instead of account-type toggle, real security bar, etc).

**Files:**
- Modify: `admin/core/src/templates/app/layout/profil_admin.html`
- Modify: `admin/core/src/app/tests_profil_view.py` (add content assertions)

- [ ] **Step 1: Add a failing content assertion**

In `admin/core/src/app/tests_profil_view.py`, add this method to `ProfilViewAccessTest`
(after `test_staff_can_view_profil_and_profil_is_created`):

```python
    def test_page_contains_expected_sections(self):
        User.objects.create_user(username='staff-content', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-content', password='motdepasse123')

        response = self.client.get(reverse('profil_admin'))

        self.assertContains(response, 'Gestion du Profil')
        self.assertContains(response, 'Informations Personnelles')
        self.assertContains(response, 'Sécurité')
        self.assertContains(response, 'Préférences')
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil_view.ProfilViewAccessTest.test_page_contains_expected_sections -v 2`
Expected: FAIL — stub template only contains "Profil", not these section titles.

- [ ] **Step 3: Write the full template**

Replace `admin/core/src/templates/app/layout/profil_admin.html` entirely:

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Profil — Portail Admin{% endblock %}

{% block styles %}
{% include 'app/includes/styles_admin.html' %}
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface">
<!-- En-tête mobile/tablette (< lg) -->
<header class="lg:hidden fixed top-0 inset-x-0 z-50 h-16 pt-safe bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center justify-between px-container-margin-mobile">
<div class="flex items-center gap-3">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<h1 class="font-headline-md text-headline-md text-primary">Profil</h1>
</div>
<div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center ml-1">
<span class="material-symbols-outlined text-on-primary text-[16px]">person</span>
</div>
</header>
{% include 'app/includes/sidebar_admin.html' with active_nav='profil' %}
<div class="lg:pl-72">
<header class="hidden lg:flex fixed top-0 left-72 right-0 h-16 bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-40 items-center justify-between px-container-margin-desktop">
<div class="flex items-center gap-base text-on-surface-variant">
<span class="material-symbols-outlined">search</span>
<input class="bg-transparent border-none outline-none font-body-md text-on-surface placeholder:text-on-surface-variant/50 w-64" placeholder="Rechercher..." type="text">
</div>
<div class="flex items-center gap-gutter">
<button class="p-2 rounded-full hover:bg-surface-container transition-colors relative">
<span class="material-symbols-outlined text-on-surface-variant">notifications</span>
<span class="absolute top-2 right-2 w-2 h-2 bg-secondary rounded-full"></span>
</button>
<div class="flex items-center gap-3 pl-4 border-l border-outline-variant">
<div class="text-right hidden sm:block">
<p class="font-label-md text-label-md text-on-surface">{{ request.user.get_full_name|default:request.user.username }}</p>
<p class="text-[11px] text-on-surface-variant">{% if request.user.is_superuser %}Super Administrateur{% else %}Administrateur{% endif %}</p>
</div>
<div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
<span class="material-symbols-outlined text-on-primary text-[18px]">person</span>
</div>
</div>
</div>
</header>
<main class="relative pt-16 pb-24 lg:pb-0 bg-surface min-h-screen">
<div class="flex flex-col w-full">
<div class="relative px-container-margin-mobile lg:px-container-margin-desktop py-section-gap overflow-hidden">
<div class="absolute top-0 right-0 -mr-16 -mt-16 w-96 h-96 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>
<div class="absolute bottom-0 left-0 -ml-16 -mb-16 w-64 h-64 bg-secondary-container/10 rounded-full blur-2xl pointer-events-none"></div>
<div class="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-base">
<div class="flex flex-col">
<span class="font-label-sm text-label-sm text-secondary uppercase tracking-[0.2em] mb-2">Paramètres</span>
<h1 class="font-display-lg text-display-lg text-primary">Gestion du Profil</h1>
</div>
{% if request.user.is_active %}
<div class="flex items-center gap-base text-on-surface-variant bg-surface-container px-4 py-2 rounded-full">
<span class="material-symbols-outlined text-[20px]">verified_user</span>
<span class="font-label-md text-label-md uppercase">Compte Vérifié</span>
</div>
{% endif %}
</div>
</div>
<div class="px-container-margin-mobile lg:px-container-margin-desktop pb-section-gap">
<form id="password-form" method="post" action="{% url 'profil_mot_de_passe' %}">{% csrf_token %}</form>
<form id="profil-form" method="post" enctype="multipart/form-data" action="{% url 'profil_admin' %}">
{% csrf_token %}
<div class="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
<!-- Colonne gauche : carte profil + sécurité -->
<div class="lg:col-span-4 flex flex-col gap-gutter">
<div class="bg-surface-container-lowest p-gutter rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col items-center text-center">
<div class="relative group">
<div class="w-32 h-32 rounded-full overflow-hidden border-4 border-surface shadow-md bg-primary-fixed flex items-center justify-center">
{% if profil.avatar %}
<img id="avatar-preview" alt="Photo de profil" class="w-full h-full object-cover" src="{{ profil.avatar.url }}">
{% else %}
<img id="avatar-preview" alt="Photo de profil" class="w-full h-full object-cover hidden">
<span id="avatar-placeholder" class="material-symbols-outlined text-on-primary-fixed-variant text-[48px]">person</span>
{% endif %}
</div>
<label for="avatar-input" class="absolute bottom-1 right-1 bg-primary text-on-primary w-10 h-10 rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition-transform cursor-pointer">
<span class="material-symbols-outlined text-[20px]">photo_camera</span>
</label>
<input type="file" name="avatar" id="avatar-input" accept="image/*" class="hidden">
</div>
<h2 class="mt-4 font-headline-md text-headline-md text-on-surface">{{ request.user.get_full_name|default:request.user.username }}</h2>
<p class="font-body-md text-on-surface-variant">Membre depuis {{ request.user.date_joined|date:"F Y"|capfirst }}</p>
<div class="w-full h-[1px] bg-outline-variant/30 my-6"></div>
<div class="w-full flex flex-col gap-base">
<div class="flex justify-between items-center px-2">
<span class="font-label-md text-label-md text-on-surface-variant">Rôle</span>
<span class="px-3 py-1 bg-primary-fixed text-on-primary-fixed-variant rounded-full font-label-sm text-label-sm">{% if request.user.is_superuser %}Super Administrateur{% else %}Administrateur{% endif %}</span>
</div>
</div>
</div>
<div class="bg-primary text-on-primary p-gutter rounded-xl shadow-md">
<div class="flex items-center gap-base mb-2">
<span class="material-symbols-outlined">security</span>
<span class="font-label-md text-label-md">Sécurité du compte</span>
</div>
<div class="w-full bg-on-primary/20 h-2 rounded-full mt-4">
<div class="bg-secondary-container h-full rounded-full shadow-[0_0_8px_rgba(254,165,32,0.6)]" style="width: {{ securite_pourcentage }}%"></div>
</div>
{% if profil.two_factor_enabled %}
<p class="text-on-primary/80 font-label-sm text-label-sm mt-3">Authentification à deux facteurs activée — sécurité maximale.</p>
{% else %}
<p class="text-on-primary/80 font-label-sm text-label-sm mt-3">Activez la 2FA ci-dessous pour atteindre 100% de sécurité.</p>
{% endif %}
</div>
</div>
<!-- Colonne droite : formulaire -->
<div class="lg:col-span-8 flex flex-col gap-gutter">
<div class="flex items-center gap-gutter overflow-x-auto pb-2 scrollbar-hide">
<a href="#informations-personnelles" class="px-6 py-3 bg-primary text-on-primary rounded-full font-label-md text-label-md whitespace-nowrap">Informations Générales</a>
<a href="#securite" class="px-6 py-3 bg-surface-container-high text-on-surface-variant rounded-full font-label-md text-label-md whitespace-nowrap hover:bg-surface-variant transition-colors">Sécurité</a>
<a href="#preferences" class="px-6 py-3 bg-surface-container-high text-on-surface-variant rounded-full font-label-md text-label-md whitespace-nowrap hover:bg-surface-variant transition-colors">Notifications</a>
</div>
<div id="informations-personnelles" class="bg-surface-container-lowest p-gutter lg:p-8 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)]">
<div class="flex items-center gap-base mb-8">
<div class="w-10 h-10 rounded-lg bg-primary-fixed flex items-center justify-center text-primary">
<span class="material-symbols-outlined">person</span>
</div>
<h3 class="font-headline-md text-headline-md text-primary">Informations Personnelles</h3>
</div>
<div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_nom_complet">Nom complet</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all font-body-md" id="id_nom_complet" name="nom_complet" type="text" value="{{ info_form.nom_complet.value|default:'' }}">
{% if info_form.nom_complet.errors %}<p class="text-error text-[12px]">{{ info_form.nom_complet.errors|join:', ' }}</p>{% endif %}
</div>
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_email">Email</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all font-body-md" id="id_email" name="email" type="email" value="{{ info_form.email.value|default:'' }}">
{% if info_form.email.errors %}<p class="text-error text-[12px]">{{ info_form.email.errors|join:', ' }}</p>{% endif %}
</div>
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_telephone">Numéro de téléphone</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary outline-none transition-all font-body-md" id="id_telephone" name="telephone" type="tel" value="{{ profil_form.telephone.value|default:'' }}">
</div>
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_ville">Ville / Commune</label>
<select class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary outline-none transition-all font-body-md" id="id_ville" name="ville">
{% for value, label in profil_form.fields.ville.choices %}
<option value="{{ value }}" {% if value == profil_form.ville.value %}selected{% endif %}>{{ label }}</option>
{% endfor %}
</select>
</div>
</div>
</div>
<div id="securite" class="bg-surface-container-lowest p-gutter lg:p-8 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)]">
<div class="flex items-center gap-base mb-8">
<div class="w-10 h-10 rounded-lg bg-error-container flex items-center justify-center text-error">
<span class="material-symbols-outlined">security</span>
</div>
<h3 class="font-headline-md text-headline-md text-primary">Sécurité</h3>
</div>
<div class="flex flex-col gap-6">
<div class="flex flex-col gap-4 p-4 rounded-lg bg-surface-container-low">
<div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
<div class="flex flex-col">
<span class="font-label-md text-label-md text-on-surface font-bold">Mot de passe</span>
<span class="font-label-sm text-label-sm text-on-surface-variant">Modifiez votre mot de passe de connexion.</span>
</div>
<button type="button" id="toggle-password-btn" class="px-6 py-2 border border-primary text-primary rounded-lg font-label-md text-label-md hover:bg-primary/5 transition-colors">Modifier le mot de passe</button>
</div>
<div id="password-fields" class="hidden grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_old_password">Mot de passe actuel</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary outline-none transition-all font-body-md" id="id_old_password" name="old_password" type="password" form="password-form">
</div>
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_new_password1">Nouveau mot de passe</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary outline-none transition-all font-body-md" id="id_new_password1" name="new_password1" type="password" form="password-form">
</div>
<div class="flex flex-col gap-2">
<label class="font-label-md text-label-md text-on-surface-variant" for="id_new_password2">Confirmation</label>
<input class="w-full h-12 px-4 rounded-lg border border-outline-variant/30 bg-surface focus:border-primary outline-none transition-all font-body-md" id="id_new_password2" name="new_password2" type="password" form="password-form">
</div>
<div class="md:col-span-3">
<button type="submit" form="password-form" class="px-6 py-2 bg-primary text-on-primary rounded-lg font-label-md text-label-md hover:bg-primary-container transition-colors">Confirmer le changement</button>
</div>
</div>
</div>
<div class="flex items-center justify-between p-4 rounded-lg border border-outline-variant/30">
<div class="flex flex-col gap-1">
<span class="font-label-md text-label-md text-on-surface font-bold">Authentification à deux facteurs</span>
<span class="font-label-sm text-label-sm text-on-surface-variant">Ajoutez une couche de sécurité supplémentaire.</span>
</div>
<label class="relative inline-flex items-center cursor-pointer">
<input class="sr-only peer" type="checkbox" name="two_factor_enabled" {% if profil_form.two_factor_enabled.value %}checked{% endif %}>
<div class="w-11 h-6 bg-surface-container-high peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
</label>
</div>
</div>
</div>
<div id="preferences" class="bg-surface-container-lowest p-gutter lg:p-8 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)]">
<div class="flex items-center gap-base mb-8">
<div class="w-10 h-10 rounded-lg bg-tertiary-fixed flex items-center justify-center text-tertiary">
<span class="material-symbols-outlined">settings_suggest</span>
</div>
<h3 class="font-headline-md text-headline-md text-primary">Préférences & Notifications</h3>
</div>
<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
<div class="flex flex-col gap-4">
<span class="font-label-md text-label-md text-on-surface font-bold">Langue du portail</span>
<div class="flex gap-2">
<label class="cursor-pointer">
<input type="radio" name="langue" value="fr" class="peer sr-only" {% if profil_form.langue.value == 'fr' %}checked{% endif %}>
<span class="block px-4 py-2 rounded-lg font-label-md text-label-md bg-surface-container-high text-on-surface-variant peer-checked:bg-primary-container peer-checked:text-on-primary-container transition-colors">Français</span>
</label>
<label class="cursor-pointer">
<input type="radio" name="langue" value="en" class="peer sr-only" {% if profil_form.langue.value == 'en' %}checked{% endif %}>
<span class="block px-4 py-2 rounded-lg font-label-md text-label-md bg-surface-container-high text-on-surface-variant peer-checked:bg-primary-container peer-checked:text-on-primary-container transition-colors">English</span>
</label>
</div>
</div>
<div class="flex flex-col gap-4">
<span class="font-label-md text-label-md text-on-surface font-bold">Canaux de notification</span>
<div class="flex flex-col gap-3">
<label class="flex items-center gap-3 cursor-pointer group">
<div class="relative w-5 h-5">
<input class="peer sr-only" type="checkbox" name="notif_email" {% if profil_form.notif_email.value %}checked{% endif %}>
<div class="w-full h-full border-2 border-outline rounded flex items-center justify-center peer-checked:bg-primary peer-checked:border-primary transition-all">
<span class="material-symbols-outlined text-white text-[16px] scale-0 peer-checked:scale-100 transition-transform">check</span>
</div>
</div>
<span class="font-body-md text-body-md text-on-surface-variant group-hover:text-on-surface">Email (Alertes, Messages)</span>
</label>
<label class="flex items-center gap-3 cursor-pointer group">
<div class="relative w-5 h-5">
<input class="peer sr-only" type="checkbox" name="notif_whatsapp" {% if profil_form.notif_whatsapp.value %}checked{% endif %}>
<div class="w-full h-full border-2 border-outline rounded flex items-center justify-center peer-checked:bg-primary peer-checked:border-primary transition-all">
<span class="material-symbols-outlined text-white text-[16px] scale-0 peer-checked:scale-100 transition-transform">check</span>
</div>
</div>
<span class="font-body-md text-body-md text-on-surface-variant group-hover:text-on-surface">WhatsApp (Demandes directes)</span>
</label>
</div>
</div>
</div>
</div>
<div class="mt-gutter flex flex-col md:flex-row items-center justify-end gap-gutter p-6 bg-surface-container-lowest rounded-xl shadow-md">
<p class="text-on-surface-variant font-label-sm text-label-sm flex-grow">Vos données sont protégées selon notre politique de confidentialité.</p>
<div class="flex gap-gutter w-full md:w-auto">
<a href="{% url 'profil_admin' %}" class="flex-1 md:flex-none px-8 py-3 text-center text-on-surface-variant font-label-md text-label-md hover:underline decoration-secondary underline-offset-4 transition-all">Annuler</a>
<button type="submit" class="flex-1 md:flex-none px-8 py-3 bg-secondary-container text-on-secondary-container font-label-md text-label-md rounded-lg shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 transition-all flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-[20px]">save</span>
Sauvegarder les modifications
</button>
</div>
</div>
</div>
</form>
</div>
</div>
</main>
</div>
{% include 'app/includes/nav_mobile_admin.html' with active_nav='profil' %}
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('toggle-password-btn').addEventListener('click', function () {
  document.getElementById('password-fields').classList.toggle('hidden');
});
document.getElementById('avatar-input').addEventListener('change', function (e) {
  var file = e.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function (ev) {
    var img = document.getElementById('avatar-preview');
    img.src = ev.target.result;
    img.classList.remove('hidden');
    var placeholder = document.getElementById('avatar-placeholder');
    if (placeholder) placeholder.classList.add('hidden');
  };
  reader.readAsDataURL(file);
});
</script>
{% endblock %}
```

- [ ] **Step 4: Run the new assertion to confirm it passes**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests_profil_view.ProfilViewAccessTest.test_page_contains_expected_sections -v 2`
Expected: `OK` (1 test)

- [ ] **Step 5: Run the full app test suite**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app -v 2`
Expected: `OK` (all tests)

- [ ] **Step 6: Commit**

```bash
git add admin/core/src/templates/app/layout/profil_admin.html admin/core/src/app/tests_profil_view.py
git commit -m "feat(admin): construit l'UI de la page Gestion du Profil"
```

---

## Task 7: Manual verification

Automated tests cover auth guards, data persistence, and template rendering, but not
actual visual layout. Run the dev server and check the golden path by hand.

- [ ] **Step 1: Run the full test suite one more time**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb -v 2`
Expected: `OK`

- [ ] **Step 2: Start the dev server**

Run (background): `cd admin/core/src && ../venv/Scripts/python.exe manage.py runserver 8000`

- [ ] **Step 3: Smoke-check the page renders and requires auth**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/profil/
```
Expected: `302` (redirect to login, not logged in).

Log in with the dev superadmin (`admin` / `admin`, per `analyse_et_taches_djona.md`) via
a browser at `http://127.0.0.1:8000/connexion/`, then visit `http://127.0.0.1:8000/profil/`
and check by hand:
- Layout matches the mockup's structure (avatar card + security widget on the left,
  tabs/sections on the right) at desktop width, and stacks to one column on mobile width.
- Editing "Nom complet"/Email/téléphone/ville and clicking "Sauvegarder les modifications"
  persists after reload.
- Uploading an avatar image shows a live preview and persists after reload.
- Toggling the 2FA switch moves the security bar between 50% and 100%.
- "Modifier le mot de passe" reveals the 3 password fields; submitting a wrong current
  password shows an error message and does not log you out; a correct change keeps you
  logged in.
- The sidebar "Settings" link (desktop and mobile) is highlighted as active on `/profil/`
  and goes back to `/tableau-de-bord/` correctly from the dashboard.

**Note:** this session has no browser/screenshot tool available, so this step must be run
by hand (or handed to a `run` skill / browser tool if one becomes available) — the
automated tests in Tasks 1–6 verify correctness of data and guards, not pixel-level visual
fidelity to the mockup.

- [ ] **Step 4: Stop the dev server**

Stop the background `runserver` process once verification is done.

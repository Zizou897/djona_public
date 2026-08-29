# Dashboard admin dynamique + habillage vendeurs/annonces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the admin dashboard's hardcoded demo numbers/lists with real data from the
existing `moderation` app mirror models (`CompteVendeur`, `AnnonceMirror`), and align
`vendeur_liste.html`/`annonce_liste.html`'s visual style with the shared admin shell
already used by `dashboard_admin.html`/`profil_admin.html`.

**Architecture:** `AdminDashboardView` gains a `get_context_data()` that queries
`vendor_db` for KPI counts, the 5 most recent pending annonces, and a composed
"recent activity" feed (vendor signups + annonce submissions, merged and sorted in
Python — no dedicated activity-log model exists). The two KPI cards with no backing
model (Séquestre, Revenu) and the "Taux de conversion" block become static "Bientôt
disponible" placeholders. `vendeur_liste.html`/`annonce_liste.html` switch to the shared
`styles_admin.html`/`sidebar_admin.html`/`nav_mobile_admin.html` includes (which gain two
new `active_nav` values: `'vendeurs'`, `'annonces'`) and get their content redrawn in the
same visual language as the rest of the portal — no view/URL/model changes on those two
pages.

**Tech Stack:** Django 5 (`admin/core`), MySQL dev DB via `vendor_db` connection
(`djona_vendor` schema, read-mostly through existing mirror models), Tailwind via CDN
(shared include), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-28-dashboard-dynamique-design.md`

---

All commands run from the repo root:

```bash
cd admin/core/src && ../venv/Scripts/python.exe manage.py <command>
```

**Test database note (same as the previous plan):** `admin/core/.env` points
`manage.py test` at a real local MySQL server shared with other checkouts. Always pass
`--keepdb` on every `manage.py test` invocation, or the command hangs waiting for
interactive input on a leftover test database.

**Cross-app import note:** `admin/core/src/app/views.py` will import from
`admin/core/src/moderation/models.py` (`from moderation.models import AnnonceMirror,
CompteVendeur`). This is a one-directional dependency (`app` → `moderation`) — `moderation`
never imports from `app`, so there is no circular import risk.

## Task 1: `AdminDashboardView` real context data

**Files:**
- Modify: `admin/core/src/app/views.py`
- Modify: `admin/core/src/app/tests.py`

- [ ] **Step 1: Write the failing tests**

Replace `admin/core/src/app/tests.py` entirely:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from moderation.models import AnnonceMirror, CompteVendeur

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


class AdminDashboardViewDataTest(TestCase):
    databases = {'default', 'vendor_db'}

    def setUp(self):
        self.admin = User.objects.create_user(username='staff-dash', password='motdepasse123', is_staff=True)
        self.client.login(username='staff-dash', password='motdepasse123')

        self.vendeur_particulier = CompteVendeur.objects.using('vendor_db').create(
            email='dash-particulier@exemple.ci', nom='Kone', prenom='Awa', telephone='0102030405',
            type_compte=CompteVendeur.TypeCompte.PARTICULIER, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-20T10:00:00Z', password='inutilise',
        )
        self.vendeur_pro = CompteVendeur.objects.using('vendor_db').create(
            email='dash-pro@exemple.ci', nom='Traore', prenom='Issa', telephone='0102030406',
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL, statut_compte=CompteVendeur.StatutCompte.ACTIF,
            is_active=True, date_joined='2026-08-27T09:00:00Z', password='inutilise',
        )

    def tearDown(self):
        AnnonceMirror.objects.using('vendor_db').filter(
            vendeur__in=[self.vendeur_particulier, self.vendeur_pro]
        ).delete()
        CompteVendeur.objects.using('vendor_db').filter(
            pk__in=[self.vendeur_particulier.pk, self.vendeur_pro.pk]
        ).delete()

    def _creer_annonce(self, statut, created_at, marque='Toyota'):
        return AnnonceMirror.objects.using('vendor_db').create(
            vendeur=self.vendeur_particulier, marque=marque, modele='Corolla', annee=2019, prix=8500000,
            kilometrage=45000, carburant='essence', boite_vitesses='automatique', couleur='Gris',
            description='Test.', statut=statut, created_at=created_at, update_at=created_at,
        )

    def test_kpi_counts_reflect_real_data(self):
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z')
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z')
        self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, '2026-08-27T09:00:00Z')

        response = self.client.get(reverse('dashboard_admin'))

        self.assertEqual(response.context['annonces_publiees'], 2)
        self.assertEqual(response.context['annonces_en_attente_total'], 1)
        self.assertEqual(response.context['annonces_total'], 3)
        self.assertEqual(response.context['vendeurs_particuliers'], 1)
        self.assertEqual(response.context['vendeurs_professionnels'], 1)
        self.assertEqual(response.context['vendeurs_total'], 2)

    def test_pending_list_shows_only_en_attente_limited_to_five(self):
        self._creer_annonce(AnnonceMirror.Statut.PUBLIEE, '2026-08-27T08:00:00Z', marque='Publiee')
        self._creer_annonce(AnnonceMirror.Statut.REFUSEE, '2026-08-27T08:00:00Z', marque='Refusee')
        for i in range(6):
            self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, f'2026-08-2{i}T09:00:00Z', marque=f'Attente{i}')

        response = self.client.get(reverse('dashboard_admin'))

        annonces_en_attente = response.context['annonces_en_attente']
        self.assertEqual(len(annonces_en_attente), 5)
        self.assertTrue(all(a.statut == AnnonceMirror.Statut.EN_ATTENTE for a in annonces_en_attente))
        self.assertNotContains(response, 'Publiee')
        self.assertNotContains(response, 'Refusee')
        # la plus récente (Attente5, 2026-08-25) doit être en tête
        self.assertEqual(annonces_en_attente[0].marque, 'Attente5')

    def test_recent_activity_combines_and_sorts_by_date(self):
        self._creer_annonce(AnnonceMirror.Statut.EN_ATTENTE, '2026-08-26T09:00:00Z', marque='Recente')

        response = self.client.get(reverse('dashboard_admin'))

        activites = response.context['activites_recentes']
        self.assertTrue(len(activites) >= 2)
        # vendeur_pro (27 août) inscrit après l'annonce (26 août) -> doit être en tête
        self.assertEqual(activites[0]['type'], 'inscription')
        self.assertIn('Issa', activites[0]['description'])
```

- [ ] **Step 2: Run it to confirm the new tests fail**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests.AdminDashboardViewDataTest -v 2`
Expected: `FAIL`/`ERROR` — `response.context['annonces_publiees']` doesn't exist yet (KeyError or `None`).

- [ ] **Step 3: Add the context data**

In `admin/core/src/app/views.py`, add the import at the top (alongside the existing
`from .forms import ...` / `from .models import ...` lines):

```python
from moderation.models import AnnonceMirror, CompteVendeur
```

Replace:

```python
class AdminDashboardView(StaffRequisMixin, TemplateView):
    template_name = 'app/layout/dashboard_admin.html'
```

with:

```python
class AdminDashboardView(StaffRequisMixin, TemplateView):
    template_name = 'app/layout/dashboard_admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        annonces_publiees = AnnonceMirror.objects.using('vendor_db').filter(
            statut=AnnonceMirror.Statut.PUBLIEE,
        ).count()
        annonces_en_attente_total = AnnonceMirror.objects.using('vendor_db').filter(
            statut=AnnonceMirror.Statut.EN_ATTENTE,
        ).count()

        vendeurs_particuliers = CompteVendeur.objects.using('vendor_db').filter(
            type_compte=CompteVendeur.TypeCompte.PARTICULIER,
        ).count()
        vendeurs_professionnels = CompteVendeur.objects.using('vendor_db').filter(
            type_compte=CompteVendeur.TypeCompte.PROFESSIONNEL,
        ).count()

        annonces_en_attente = list(
            AnnonceMirror.objects.using('vendor_db')
            .filter(statut=AnnonceMirror.Statut.EN_ATTENTE)
            .select_related('vendeur')
            .order_by('-created_at')[:5]
        )

        activites = []
        for vendeur in CompteVendeur.objects.using('vendor_db').order_by('-date_joined')[:6]:
            activites.append({
                'type': 'inscription',
                'titre': 'Nouvelle inscription vendeur',
                'description': (
                    f'{vendeur.prenom} {vendeur.nom} a créé un compte '
                    f'{vendeur.get_type_compte_display().lower()}.'
                ),
                'date': vendeur.date_joined,
            })
        for annonce in (
            AnnonceMirror.objects.using('vendor_db')
            .select_related('vendeur')
            .order_by('-created_at')[:6]
        ):
            activites.append({
                'type': 'annonce',
                'titre': 'Nouvelle annonce',
                'description': (
                    f'Annonce {annonce.marque} {annonce.modele} soumise par '
                    f'{annonce.vendeur.prenom} {annonce.vendeur.nom}.'
                ),
                'date': annonce.created_at,
            })
        activites.sort(key=lambda evenement: evenement['date'], reverse=True)

        context.update({
            'annonces_publiees': annonces_publiees,
            'annonces_en_attente_total': annonces_en_attente_total,
            'annonces_total': annonces_publiees + annonces_en_attente_total,
            'vendeurs_particuliers': vendeurs_particuliers,
            'vendeurs_professionnels': vendeurs_professionnels,
            'vendeurs_total': vendeurs_particuliers + vendeurs_professionnels,
            'annonces_en_attente': annonces_en_attente,
            'activites_recentes': activites[:6],
        })
        return context
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests: 3 access + 3 data)

- [ ] **Step 5: Commit**

```bash
git add admin/core/src/app/views.py admin/core/src/app/tests.py
git commit -m "feat(admin): AdminDashboardView expose des donnees reelles (annonces, vendeurs, activite)"
```

---

## Task 2: Dashboard template — KPI cards

**Files:**
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Confirm baseline**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests, from Task 1)

- [ ] **Step 2: Replace the 4 KPI cards**

Replace this block (the `<!-- Chiffres de démo ... -->` comment through the closing of
the 4-card `<section>`):

```html
<!-- Chiffres de démo en attendant les modèles Annonce/Utilisateur/Transaction (voir analyse_et_taches_djona.md, section D) -->
<section class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-gutter px-container-margin-mobile md:px-container-margin-desktop py-base">
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300">
<div class="flex items-center justify-between">
<div class="p-3 bg-primary-fixed rounded-lg text-on-primary-fixed-variant">
<span class="material-symbols-outlined text-[28px]">directions_car</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Total Annonces</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-primary leading-none">1,284</h2>
<div class="flex gap-4 mt-2">
<span class="font-label-md text-label-md text-primary flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-primary"></span> 842 actives</span>
<span class="font-label-md text-label-md text-secondary flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-secondary"></span> 442 en attente</span>
</div>
</div>
</div>
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300">
<div class="flex items-center justify-between">
<div class="p-3 bg-tertiary-fixed rounded-lg text-on-tertiary-fixed">
<span class="material-symbols-outlined text-[28px]">group</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Communauté</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-primary leading-none">5,902</h2>
<div class="flex gap-4 mt-2 text-on-surface-variant">
<span class="font-label-md text-label-md">3.2k vendeurs</span>
<span class="font-label-md text-label-md">2.7k acheteurs</span>
</div>
</div>
</div>
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300 border-l-4 border-secondary">
<div class="flex items-center justify-between">
<div class="p-3 bg-secondary-fixed rounded-lg text-on-secondary-fixed">
<span class="material-symbols-outlined text-[28px]">payments</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Séquestre en cours</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-primary leading-none">42</h2>
<p class="font-label-md text-label-md text-secondary mt-2">Transactions Djona actives</p>
</div>
</div>
<div class="bg-primary p-6 rounded-xl shadow-xl flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300">
<div class="flex items-center justify-between">
<div class="p-3 bg-on-primary/10 rounded-lg text-on-primary">
<span class="material-symbols-outlined text-[28px]">trending_up</span>
</div>
<span class="font-label-sm text-label-sm text-on-primary/60 uppercase tracking-widest">Revenu (semaine)</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-on-primary leading-none">8.4M<span class="text-headline-md ml-1">CFA</span></h2>
<div class="flex items-center gap-1 text-on-primary-container mt-2">
<span class="material-symbols-outlined text-sm">arrow_upward</span>
<span class="font-label-md text-label-md">+12.5% vs semaine dernière</span>
</div>
</div>
</div>
</section>
```

with:

```html
<section class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-gutter px-container-margin-mobile md:px-container-margin-desktop py-base">
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300">
<div class="flex items-center justify-between">
<div class="p-3 bg-primary-fixed rounded-lg text-on-primary-fixed-variant">
<span class="material-symbols-outlined text-[28px]">directions_car</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Total Annonces</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-primary leading-none">{{ annonces_total }}</h2>
<div class="flex gap-4 mt-2">
<span class="font-label-md text-label-md text-primary flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-primary"></span> {{ annonces_publiees }} publiées</span>
<span class="font-label-md text-label-md text-secondary flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-secondary"></span> {{ annonces_en_attente_total }} en attente</span>
</div>
</div>
</div>
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 group hover:-translate-y-1 transition-all duration-300">
<div class="flex items-center justify-between">
<div class="p-3 bg-tertiary-fixed rounded-lg text-on-tertiary-fixed">
<span class="material-symbols-outlined text-[28px]">group</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Communauté</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-primary leading-none">{{ vendeurs_total }}</h2>
<div class="flex gap-4 mt-2 text-on-surface-variant">
<span class="font-label-md text-label-md">{{ vendeurs_particuliers }} particuliers</span>
<span class="font-label-md text-label-md">{{ vendeurs_professionnels }} professionnels</span>
</div>
</div>
</div>
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 border-l-4 border-outline-variant/40">
<div class="flex items-center justify-between">
<div class="p-3 bg-surface-container rounded-lg text-on-surface-variant">
<span class="material-symbols-outlined text-[28px]">payments</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Séquestre en cours</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-on-surface-variant leading-none">—</h2>
<p class="font-label-md text-label-md text-on-surface-variant mt-2">Bientôt disponible</p>
</div>
</div>
<div class="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] flex flex-col gap-4 border-l-4 border-outline-variant/40">
<div class="flex items-center justify-between">
<div class="p-3 bg-surface-container rounded-lg text-on-surface-variant">
<span class="material-symbols-outlined text-[28px]">trending_up</span>
</div>
<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Revenu (semaine)</span>
</div>
<div>
<h2 class="font-display-lg text-display-lg text-on-surface-variant leading-none">—</h2>
<p class="font-label-md text-label-md text-on-surface-variant mt-2">Bientôt disponible</p>
</div>
</div>
</section>
```

- [ ] **Step 3: Replace the "Taux de conversion" gradient block**

Replace:

```html
<div class="bg-gradient-to-br from-primary to-primary-container p-6 rounded-2xl text-on-primary relative overflow-hidden group">
<div class="absolute -right-4 -top-4 w-24 h-24 bg-on-primary/10 rounded-full blur-2xl group-hover:scale-150 transition-transform duration-700"></div>
<h4 class="font-label-sm text-label-sm uppercase tracking-widest mb-4 opacity-70">Taux de conversion</h4>
<div class="flex items-end gap-3 mb-6">
<span class="font-display-lg text-display-lg leading-none">64.2%</span>
<span class="font-label-md text-label-md mb-2 flex items-center text-secondary-fixed"><span class="material-symbols-outlined text-sm">trending_up</span> +2.1%</span>
</div>
<div class="w-full bg-on-primary/20 h-2 rounded-full overflow-hidden">
<div class="bg-secondary-container h-full rounded-full" style="width: 64.2%"></div>
</div>
<p class="mt-4 font-label-sm text-[11px] opacity-60">Ratio annonce → transaction vérifiée ce mois-ci</p>
</div>
```

with:

```html
<div class="bg-surface-container p-6 rounded-2xl text-on-surface-variant relative overflow-hidden">
<h4 class="font-label-sm text-label-sm uppercase tracking-widest mb-4 opacity-70">Taux de conversion</h4>
<p class="font-body-md text-body-md">Bientôt disponible — nécessite le module Transactions.</p>
</div>
```

- [ ] **Step 4: Run the test suite to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 5: Commit**

```bash
git add admin/core/src/templates/app/layout/dashboard_admin.html
git commit -m "feat(admin): cartes KPI du dashboard branchees sur des donnees reelles"
```

---

## Task 3: Dashboard template — "Validation en attente"

**Files:**
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Replace the desktop table body**

Replace the `<tbody>` block (the 3 hardcoded `<tr>` rows for Koffi Alain / Marie Diallo /
Bakayoko Traoré, inside `<div class="hidden lg:block overflow-x-auto">`):

```html
<tbody class="divide-y divide-surface-container">
<tr class="hover:bg-surface transition-colors">
<td class="px-6 py-4 font-label-md text-label-md whitespace-nowrap">24 Oct, 14:30</td>
<td class="px-6 py-4"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">KA</div><span class="font-label-md text-label-md">Koffi Alain</span></div></td>
<td class="px-6 py-4"><p class="font-label-md text-label-md text-on-surface">Toyota RAV4 2022</p><p class="text-[11px] text-on-surface-variant">45,000 km • Essence</p></td>
<td class="px-6 py-4 font-label-md text-label-md text-right text-primary">18,500,000 CFA</td>
<td class="px-6 py-4"><span class="px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span></td>
<td class="px-6 py-4 text-right"><div class="flex justify-end gap-2">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div></td>
</tr>
<tr class="hover:bg-surface transition-colors">
<td class="px-6 py-4 font-label-md text-label-md whitespace-nowrap">24 Oct, 12:15</td>
<td class="px-6 py-4"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center font-bold text-[12px]">MD</div><span class="font-label-md text-label-md">Marie Diallo</span></div></td>
<td class="px-6 py-4"><p class="font-label-md text-label-md text-on-surface">Mercedes C300 2019</p><p class="text-[11px] text-on-surface-variant">72,000 km • Essence</p></td>
<td class="px-6 py-4 font-label-md text-label-md text-right text-primary">22,000,000 CFA</td>
<td class="px-6 py-4"><span class="px-3 py-1 rounded-full bg-surface-container-high text-on-surface-variant text-[12px] font-bold uppercase tracking-tighter">Révision</span></td>
<td class="px-6 py-4 text-right"><div class="flex justify-end gap-2">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div></td>
</tr>
<tr class="hover:bg-surface transition-colors">
<td class="px-6 py-4 font-label-md text-label-md whitespace-nowrap">23 Oct, 18:45</td>
<td class="px-6 py-4"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-bold text-[12px]">BT</div><span class="font-label-md text-label-md">Bakayoko Traoré</span></div></td>
<td class="px-6 py-4"><p class="font-label-md text-label-md text-on-surface">Range Rover Sport 2021</p><p class="text-[11px] text-on-surface-variant">31,000 km • Diesel</p></td>
<td class="px-6 py-4 font-label-md text-label-md text-right text-primary">45,000,000 CFA</td>
<td class="px-6 py-4"><span class="px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span></td>
<td class="px-6 py-4 text-right"><div class="flex justify-end gap-2">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div></td>
</tr>
</tbody>
```

with:

```html
<tbody class="divide-y divide-surface-container">
{% for annonce in annonces_en_attente %}
<tr class="hover:bg-surface transition-colors">
<td class="px-6 py-4 font-label-md text-label-md whitespace-nowrap">{{ annonce.created_at|date:"d M, H:i" }}</td>
<td class="px-6 py-4"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">{{ annonce.vendeur.prenom|first|upper }}{{ annonce.vendeur.nom|first|upper }}</div><span class="font-label-md text-label-md">{{ annonce.vendeur.prenom }} {{ annonce.vendeur.nom }}</span></div></td>
<td class="px-6 py-4"><p class="font-label-md text-label-md text-on-surface">{{ annonce.marque }} {{ annonce.modele }} {{ annonce.annee }}</p><p class="text-[11px] text-on-surface-variant">{{ annonce.kilometrage }} km • {{ annonce.get_carburant_display }}</p></td>
<td class="px-6 py-4 font-label-md text-label-md text-right text-primary">{{ annonce.prix }} CFA</td>
<td class="px-6 py-4"><span class="px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span></td>
<td class="px-6 py-4 text-right"><div class="flex justify-end gap-2">
<form method="post" action="{% url 'annonce_valider' annonce.pk %}" class="inline">{% csrf_token %}<button type="submit" class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button></form>
<form method="post" action="{% url 'annonce_refuser' annonce.pk %}" class="inline">{% csrf_token %}<button type="submit" class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button></form>
<a href="{% url 'annonce_moderation_detail' annonce.pk %}" class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></a>
</div></td>
</tr>
{% empty %}
<tr><td class="px-6 py-8 text-center text-on-surface-variant" colspan="6">Aucune annonce en attente de validation.</td></tr>
{% endfor %}
</tbody>
```

- [ ] **Step 2: Replace the mobile cards block**

Replace (the `<div class="lg:hidden flex flex-col divide-y divide-surface-container">`
through its closing `</div>`, i.e. the 3 hardcoded mobile cards, but keep the trailing
"Voir toutes les annonces en attente" footer `<div>` — see next step):

```html
<div class="lg:hidden flex flex-col divide-y divide-surface-container">
<div class="p-4 flex flex-col gap-3">
<div class="flex items-start justify-between gap-3">
<div class="flex items-center gap-3 min-w-0">
<div class="w-9 h-9 flex-none rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">KA</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">Koffi Alain</p>
<p class="text-[11px] text-on-surface-variant">24 Oct, 14:30</p>
</div>
</div>
<span class="flex-none px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
</div>
<div>
<p class="font-label-md text-label-md text-on-surface">Toyota RAV4 2022</p>
<p class="text-[11px] text-on-surface-variant">45,000 km • Essence</p>
</div>
<div class="flex items-center justify-between">
<span class="font-label-md text-label-md text-primary">18,500,000 CFA</span>
<div class="flex gap-1">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div>
</div>
</div>
<div class="p-4 flex flex-col gap-3">
<div class="flex items-start justify-between gap-3">
<div class="flex items-center gap-3 min-w-0">
<div class="w-9 h-9 flex-none rounded-full bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center font-bold text-[12px]">MD</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">Marie Diallo</p>
<p class="text-[11px] text-on-surface-variant">24 Oct, 12:15</p>
</div>
</div>
<span class="flex-none px-3 py-1 rounded-full bg-surface-container-high text-on-surface-variant text-[12px] font-bold uppercase tracking-tighter">Révision</span>
</div>
<div>
<p class="font-label-md text-label-md text-on-surface">Mercedes C300 2019</p>
<p class="text-[11px] text-on-surface-variant">72,000 km • Essence</p>
</div>
<div class="flex items-center justify-between">
<span class="font-label-md text-label-md text-primary">22,000,000 CFA</span>
<div class="flex gap-1">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div>
</div>
</div>
<div class="p-4 flex flex-col gap-3">
<div class="flex items-start justify-between gap-3">
<div class="flex items-center gap-3 min-w-0">
<div class="w-9 h-9 flex-none rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-bold text-[12px]">BT</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">Bakayoko Traoré</p>
<p class="text-[11px] text-on-surface-variant">23 Oct, 18:45</p>
</div>
</div>
<span class="flex-none px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
</div>
<div>
<p class="font-label-md text-label-md text-on-surface">Range Rover Sport 2021</p>
<p class="text-[11px] text-on-surface-variant">31,000 km • Diesel</p>
</div>
<div class="flex items-center justify-between">
<span class="font-label-md text-label-md text-primary">45,000,000 CFA</span>
<div class="flex gap-1">
<button class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button>
<button class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button>
<button class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></button>
</div>
</div>
</div>
</div>
<div class="p-4 border-t border-surface-container flex items-center justify-center">
<button class="text-primary font-label-md text-label-md hover:underline">Voir toutes les annonces en attente</button>
</div>
```

with:

```html
<div class="lg:hidden flex flex-col divide-y divide-surface-container">
{% for annonce in annonces_en_attente %}
<div class="p-4 flex flex-col gap-3">
<div class="flex items-start justify-between gap-3">
<div class="flex items-center gap-3 min-w-0">
<div class="w-9 h-9 flex-none rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">{{ annonce.vendeur.prenom|first|upper }}{{ annonce.vendeur.nom|first|upper }}</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">{{ annonce.vendeur.prenom }} {{ annonce.vendeur.nom }}</p>
<p class="text-[11px] text-on-surface-variant">{{ annonce.created_at|date:"d M, H:i" }}</p>
</div>
</div>
<span class="flex-none px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
</div>
<div>
<p class="font-label-md text-label-md text-on-surface">{{ annonce.marque }} {{ annonce.modele }} {{ annonce.annee }}</p>
<p class="text-[11px] text-on-surface-variant">{{ annonce.kilometrage }} km • {{ annonce.get_carburant_display }}</p>
</div>
<div class="flex items-center justify-between">
<span class="font-label-md text-label-md text-primary">{{ annonce.prix }} CFA</span>
<div class="flex gap-1">
<form method="post" action="{% url 'annonce_valider' annonce.pk %}" class="inline">{% csrf_token %}<button type="submit" class="p-2 hover:bg-primary-container hover:text-on-primary transition-colors rounded-lg text-primary-container" title="Valider"><span class="material-symbols-outlined text-[20px]">check_circle</span></button></form>
<form method="post" action="{% url 'annonce_refuser' annonce.pk %}" class="inline">{% csrf_token %}<button type="submit" class="p-2 hover:bg-error-container hover:text-error transition-colors rounded-lg text-on-surface-variant" title="Refuser"><span class="material-symbols-outlined text-[20px]">cancel</span></button></form>
<a href="{% url 'annonce_moderation_detail' annonce.pk %}" class="p-2 hover:bg-surface-container-high transition-colors rounded-lg text-on-surface-variant" title="Voir le détail"><span class="material-symbols-outlined text-[20px]">visibility</span></a>
</div>
</div>
</div>
{% empty %}
<div class="p-8 text-center text-on-surface-variant">Aucune annonce en attente de validation.</div>
{% endfor %}
</div>
<div class="p-4 border-t border-surface-container flex items-center justify-center">
<a href="{% url 'annonce_moderation_liste' %}" class="text-primary font-label-md text-label-md hover:underline">Voir toutes les annonces en attente</a>
</div>
```

- [ ] **Step 3: Run the tests**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 4: Commit**

```bash
git add admin/core/src/templates/app/layout/dashboard_admin.html
git commit -m "feat(admin): section Validation en attente du dashboard branchee sur des annonces reelles"
```

---

## Task 4: Dashboard template — "Activité récente"

**Files:**
- Modify: `admin/core/src/templates/app/layout/dashboard_admin.html`

- [ ] **Step 1: Replace the activity feed**

Replace (the 4 hardcoded activity entries plus the "Charger plus d'activité" button,
inside the `<h3>Activité récente</h3>` card):

```html
<div class="space-y-6 relative before:absolute before:left-[19px] before:top-2 before:bottom-2 before:w-[2px] before:bg-surface-container">
<div class="relative flex gap-4">
<div class="relative z-10 w-10 h-10 rounded-full bg-primary flex items-center justify-center shadow-lg"><span class="material-symbols-outlined text-on-primary text-[18px]">person_add</span></div>
<div><p class="font-label-md text-label-md text-on-surface">Nouvelle inscription vendeur</p><p class="font-body-md text-body-md text-on-surface-variant text-[13px]">Abdoulaye Kouadio a inscrit un compte concessionnaire.</p><span class="text-[11px] font-bold text-secondary uppercase mt-1 block">Il y a 2 minutes</span></div>
</div>
<div class="relative flex gap-4">
<div class="relative z-10 w-10 h-10 rounded-full bg-secondary flex items-center justify-center shadow-lg"><span class="material-symbols-outlined text-on-secondary text-[18px]">campaign</span></div>
<div><p class="font-label-md text-label-md text-on-surface">Nouvelle annonce</p><p class="font-body-md text-body-md text-on-surface-variant text-[13px]">Annonce Toyota Camry soumise pour révision par AutoPlus.</p><span class="text-[11px] font-bold text-on-surface-variant uppercase mt-1 block">Il y a 15 minutes</span></div>
</div>
<div class="relative flex gap-4">
<div class="relative z-10 w-10 h-10 rounded-full bg-primary-fixed-dim flex items-center justify-center shadow-lg"><span class="material-symbols-outlined text-on-primary-fixed-variant text-[18px]">shopping_cart_checkout</span></div>
<div><p class="font-label-md text-label-md text-on-surface">Transaction démarrée</p><p class="font-body-md text-body-md text-on-surface-variant text-[13px]">Séquestre Djona Safe initié pour BMW X5 - ID #8921.</p><span class="text-[11px] font-bold text-on-surface-variant uppercase mt-1 block">Il y a 1 heure</span></div>
</div>
<div class="relative flex gap-4 opacity-70">
<div class="relative z-10 w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center shadow-sm"><span class="material-symbols-outlined text-on-surface-variant text-[18px]">verified_user</span></div>
<div><p class="font-label-md text-label-md text-on-surface">Utilisateur vérifié</p><p class="font-body-md text-body-md text-on-surface-variant text-[13px]">Vérification d'identité de Seydou Bamba terminée avec succès.</p><span class="text-[11px] font-bold text-on-surface-variant uppercase mt-1 block">Il y a 3 heures</span></div>
</div>
</div>
<button class="w-full mt-8 py-3 bg-surface-container rounded-xl font-label-md text-label-md text-primary hover:bg-primary hover:text-on-primary transition-all flex items-center justify-center gap-2">
Charger plus d'activité <span class="material-symbols-outlined text-[18px]">expand_more</span>
</button>
```

with:

```html
<div class="space-y-6 relative before:absolute before:left-[19px] before:top-2 before:bottom-2 before:w-[2px] before:bg-surface-container">
{% for evenement in activites_recentes %}
<div class="relative flex gap-4">
<div class="relative z-10 w-10 h-10 rounded-full {% if evenement.type == 'inscription' %}bg-primary{% else %}bg-secondary{% endif %} flex items-center justify-center shadow-lg"><span class="material-symbols-outlined {% if evenement.type == 'inscription' %}text-on-primary{% else %}text-on-secondary{% endif %} text-[18px]">{% if evenement.type == 'inscription' %}person_add{% else %}campaign{% endif %}</span></div>
<div><p class="font-label-md text-label-md text-on-surface">{{ evenement.titre }}</p><p class="font-body-md text-body-md text-on-surface-variant text-[13px]">{{ evenement.description }}</p><span class="text-[11px] font-bold text-secondary uppercase mt-1 block">Il y a {{ evenement.date|timesince }}</span></div>
</div>
{% empty %}
<p class="text-on-surface-variant text-center py-8">Aucune activité récente.</p>
{% endfor %}
</div>
```

- [ ] **Step 2: Run the tests**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 3: Commit**

```bash
git add admin/core/src/templates/app/layout/dashboard_admin.html
git commit -m "feat(admin): section Activite recente du dashboard branchee sur des donnees reelles"
```

---

## Task 5: Shared includes — `active_nav` support for `'vendeurs'`/`'annonces'`

**Files:**
- Modify: `admin/core/src/templates/app/includes/sidebar_admin.html`
- Modify: `admin/core/src/templates/app/includes/nav_mobile_admin.html`

- [ ] **Step 1: Confirm baseline**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app.tests -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 2: Update `sidebar_admin.html`**

Replace:

```html
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Annonces à valider</span>
</a>
<a class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Vendeurs</span>
</a>
```

with:

```html
<a {% if active_nav == 'annonces' %}aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm"{% else %}class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all"{% endif %} href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined mr-4">fact_check</span><span class="font-label-md text-label-md">Annonces à valider</span>
</a>
<a {% if active_nav == 'vendeurs' %}aria-current="page" class="flex items-center px-4 py-3 rounded-lg transition-all bg-secondary-container text-on-secondary-container font-bold shadow-sm"{% else %}class="flex items-center px-4 py-3 rounded-lg text-on-primary/70 hover:bg-primary-container hover:text-on-primary transition-all"{% endif %} href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined mr-4">group</span><span class="font-label-md text-label-md">Vendeurs</span>
</a>
```

- [ ] **Step 3: Update `nav_mobile_admin.html`**

Replace:

```html
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
<a class="flex flex-col items-center justify-center gap-1 text-on-surface-variant" href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Vendeurs</span>
</a>
```

with:

```html
<a {% if active_nav == 'annonces' %}aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary"{% else %}class="flex flex-col items-center justify-center gap-1 text-on-surface-variant"{% endif %} href="{% url 'annonce_moderation_liste' %}">
<span class="material-symbols-outlined">fact_check</span><span class="font-label-sm text-label-sm">Validation</span>
</a>
<a {% if active_nav == 'vendeurs' %}aria-current="page" class="flex flex-col items-center justify-center gap-1 text-secondary"{% else %}class="flex flex-col items-center justify-center gap-1 text-on-surface-variant"{% endif %} href="{% url 'vendeur_liste' %}">
<span class="material-symbols-outlined">group</span><span class="font-label-sm text-label-sm">Vendeurs</span>
</a>
```

- [ ] **Step 4: Run the full app test suite to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb app -v 2`
Expected: `OK` (all `app` tests — a broken include would turn `test_staff_can_view_dashboard`
and the Task 6/7 profile tests into failures/500s)

- [ ] **Step 5: Commit**

```bash
git add admin/core/src/templates/app/includes/sidebar_admin.html admin/core/src/templates/app/includes/nav_mobile_admin.html
git commit -m "feat(admin): active_nav vendeurs/annonces dans les includes partages"
```

---

## Task 6: `vendeur_liste.html` — habillage partagé

**Files:**
- Modify: `admin/core/src/templates/moderation/vendeur_liste.html`

- [ ] **Step 1: Confirm baseline**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb moderation -v 2`
Expected: `OK` (all `moderation` tests, including `VendeurListViewTest`)

- [ ] **Step 2: Replace the whole file**

Replace `admin/core/src/templates/moderation/vendeur_liste.html` entirely:

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Vendeurs — Portail Admin{% endblock %}

{% block styles %}
{% include 'app/includes/styles_admin.html' %}
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface">
<!-- En-tête mobile/tablette (< lg) -->
<header class="lg:hidden fixed top-0 inset-x-0 z-50 h-16 pt-safe bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center justify-between px-container-margin-mobile">
<div class="flex items-center gap-3">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<h1 class="font-headline-md text-headline-md text-primary">Vendeurs</h1>
</div>
<div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center ml-1">
<span class="material-symbols-outlined text-on-primary text-[16px]">person</span>
</div>
</header>
{% include 'app/includes/sidebar_admin.html' with active_nav='vendeurs' %}
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
<div class="px-container-margin-mobile lg:px-container-margin-desktop py-section-gap">
<span class="font-label-sm text-label-sm text-secondary uppercase tracking-[0.2em] mb-2 block">Communauté</span>
<h1 class="font-display-lg text-display-lg text-primary mb-8">Vendeurs</h1>
<div class="bg-surface-container-lowest rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] overflow-hidden">
<div class="hidden lg:block overflow-x-auto">
<table class="w-full text-left border-collapse">
<thead>
<tr class="border-b border-surface-variant">
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Nom</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Email</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Téléphone</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Type</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Inscription</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Statut</th>
<th class="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider text-right">Action</th>
</tr>
</thead>
<tbody class="divide-y divide-surface-container">
{% for vendeur in vendeurs %}
<tr class="hover:bg-surface transition-colors">
<td class="px-6 py-4"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">{{ vendeur.prenom|first|upper }}{{ vendeur.nom|first|upper }}</div><span class="font-label-md text-label-md">{{ vendeur.prenom }} {{ vendeur.nom }}</span></div></td>
<td class="px-6 py-4 text-on-surface-variant">{{ vendeur.email }}</td>
<td class="px-6 py-4 text-on-surface-variant">{{ vendeur.telephone }}</td>
<td class="px-6 py-4 font-label-md text-label-md">{{ vendeur.get_type_compte_display }}</td>
<td class="px-6 py-4 text-on-surface-variant font-label-md text-label-md">{{ vendeur.date_joined|date:'d/m/Y' }}</td>
<td class="px-6 py-4">
{% if vendeur.statut_compte == 'en_attente' %}
<span class="px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
{% elif vendeur.statut_compte == 'actif' %}
<span class="px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed-variant text-[12px] font-bold uppercase tracking-tighter">Actif</span>
{% else %}
<span class="px-3 py-1 rounded-full bg-error-container text-error text-[12px] font-bold uppercase tracking-tighter">Suspendu</span>
{% endif %}
</td>
<td class="px-6 py-4 text-right">
{% if vendeur.statut_compte != 'actif' %}
<form action="{% url 'vendeur_activer' vendeur.pk %}" method="post" class="inline">
{% csrf_token %}
<button class="px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors" type="submit">Activer</button>
</form>
{% else %}
<form action="{% url 'vendeur_suspendre' vendeur.pk %}" method="post" class="inline">
{% csrf_token %}
<button class="px-4 py-2 rounded-lg border border-error text-error font-label-md text-label-md hover:bg-error-container/20 transition-colors" type="submit">Suspendre</button>
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
<!-- Cartes : mobile/tablette uniquement (< lg) -->
<div class="lg:hidden flex flex-col divide-y divide-surface-container">
{% for vendeur in vendeurs %}
<div class="p-4 flex flex-col gap-3">
<div class="flex items-start justify-between gap-3">
<div class="flex items-center gap-3 min-w-0">
<div class="w-9 h-9 flex-none rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">{{ vendeur.prenom|first|upper }}{{ vendeur.nom|first|upper }}</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">{{ vendeur.prenom }} {{ vendeur.nom }}</p>
<p class="text-[11px] text-on-surface-variant truncate">{{ vendeur.email }}</p>
</div>
</div>
{% if vendeur.statut_compte == 'en_attente' %}
<span class="flex-none px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
{% elif vendeur.statut_compte == 'actif' %}
<span class="flex-none px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed-variant text-[12px] font-bold uppercase tracking-tighter">Actif</span>
{% else %}
<span class="flex-none px-3 py-1 rounded-full bg-error-container text-error text-[12px] font-bold uppercase tracking-tighter">Suspendu</span>
{% endif %}
</div>
<div class="flex items-center justify-between text-[13px] text-on-surface-variant">
<span>{{ vendeur.telephone }}</span>
<span>{{ vendeur.get_type_compte_display }} · {{ vendeur.date_joined|date:'d/m/Y' }}</span>
</div>
<div>
{% if vendeur.statut_compte != 'actif' %}
<form action="{% url 'vendeur_activer' vendeur.pk %}" method="post">
{% csrf_token %}
<button class="w-full px-4 py-2 rounded-lg bg-primary text-on-primary font-label-md text-label-md hover:bg-primary-container transition-colors" type="submit">Activer</button>
</form>
{% else %}
<form action="{% url 'vendeur_suspendre' vendeur.pk %}" method="post">
{% csrf_token %}
<button class="w-full px-4 py-2 rounded-lg border border-error text-error font-label-md text-label-md hover:bg-error-container/20 transition-colors" type="submit">Suspendre</button>
</form>
{% endif %}
</div>
</div>
{% empty %}
<div class="p-8 text-center text-on-surface-variant">Aucun vendeur inscrit pour le moment.</div>
{% endfor %}
</div>
</div>
</div>
</div>
</main>
</div>
{% include 'app/includes/nav_mobile_admin.html' with active_nav='vendeurs' %}
</div>
{% endblock %}
```

- [ ] **Step 3: Run the moderation test suite to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb moderation -v 2`
Expected: `OK` (all `moderation` tests — `VendeurListViewTest` checks `assertContains`/
`assertRedirects`/ordering, none of which depend on the removed inline styles)

- [ ] **Step 4: Commit**

```bash
git add admin/core/src/templates/moderation/vendeur_liste.html
git commit -m "style(admin): habillage partage pour la page Vendeurs"
```

---

## Task 7: `annonce_liste.html` — habillage partagé

**Files:**
- Modify: `admin/core/src/templates/moderation/annonce_liste.html`

- [ ] **Step 1: Confirm baseline**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb moderation -v 2`
Expected: `OK` (all `moderation` tests, including `AnnonceModerationListViewTest`)

- [ ] **Step 2: Replace the whole file**

Replace `admin/core/src/templates/moderation/annonce_liste.html` entirely:

```html
{% extends 'app/base/base.html' %}
{% load static %}

{% block title %}Annonces à valider — Portail Admin{% endblock %}

{% block styles %}
{% include 'app/includes/styles_admin.html' %}
{% endblock %}

{% block content %}
<div class="bg-surface font-body-md text-on-surface">
<!-- En-tête mobile/tablette (< lg) -->
<header class="lg:hidden fixed top-0 inset-x-0 z-50 h-16 pt-safe bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center justify-between px-container-margin-mobile">
<div class="flex items-center gap-3">
<img alt="Djona" class="h-8 w-8 object-contain rounded-lg" src="{% static 'app/assets/img/djona-logo.png' %}">
<h1 class="font-headline-md text-headline-md text-primary">Validation</h1>
</div>
<div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center ml-1">
<span class="material-symbols-outlined text-on-primary text-[16px]">person</span>
</div>
</header>
{% include 'app/includes/sidebar_admin.html' with active_nav='annonces' %}
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
<div class="px-container-margin-mobile lg:px-container-margin-desktop py-section-gap">
<span class="font-label-sm text-label-sm text-secondary uppercase tracking-[0.2em] mb-2 block">Modération</span>
<h1 class="font-display-lg text-display-lg text-primary mb-8">Annonces à valider</h1>
<div class="flex flex-col gap-gutter">
{% for annonce in annonces %}
<a class="bg-surface-container-lowest rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] p-5 flex items-center justify-between gap-4 hover:-translate-y-0.5 transition-all" href="{% url 'annonce_moderation_detail' annonce.pk %}">
<div class="flex items-center gap-4 min-w-0">
<div class="w-10 h-10 flex-none rounded-full bg-primary-fixed-dim text-on-primary-fixed-variant flex items-center justify-center font-bold text-[12px]">{{ annonce.vendeur.prenom|first|upper }}{{ annonce.vendeur.nom|first|upper }}</div>
<div class="min-w-0">
<p class="font-label-md text-label-md text-on-surface truncate">{{ annonce.marque }} {{ annonce.modele }} ({{ annonce.annee }})</p>
<p class="text-[13px] text-on-surface-variant truncate">{{ annonce.vendeur.prenom }} {{ annonce.vendeur.nom }} · {{ annonce.prix }} CFA</p>
</div>
</div>
<span class="flex-none px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold uppercase tracking-tighter">En attente</span>
</a>
{% empty %}
<div class="bg-surface-container-lowest rounded-xl shadow-[0_4px_12px_rgba(26,82,118,0.08)] text-center py-16 text-on-surface-variant">Aucune annonce en attente de validation.</div>
{% endfor %}
</div>
</div>
</div>
</main>
</div>
{% include 'app/includes/nav_mobile_admin.html' with active_nav='annonces' %}
</div>
{% endblock %}
```

- [ ] **Step 3: Run the moderation test suite to confirm no regression**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb moderation -v 2`
Expected: `OK` (all `moderation` tests)

- [ ] **Step 4: Commit**

```bash
git add admin/core/src/templates/moderation/annonce_liste.html
git commit -m "style(admin): habillage partage pour la page Annonces a valider"
```

---

## Task 8: Manual verification

- [ ] **Step 1: Run the full test suite one more time**

Run: `cd admin/core/src && ../venv/Scripts/python.exe manage.py test --keepdb -v 2`
Expected: `OK`

- [ ] **Step 2: Start the dev server**

Run (background): `cd admin/core/src && ../venv/Scripts/python.exe manage.py runserver 8000`

- [ ] **Step 3: Check by hand**

Log in as staff at `http://127.0.0.1:8000/connexion/`, then visit:
- `http://127.0.0.1:8000/tableau-de-bord/` — KPI cards show real counts (compare against
  `manage.py shell` counts of `AnnonceMirror`/`CompteVendeur` on `vendor_db` if in doubt);
  Séquestre/Revenu/Taux de conversion show "Bientôt disponible"; "Validation en attente"
  shows real pending annonces with working Valider/Refuser/Voir buttons; "Activité
  récente" shows a real, date-sorted feed; no leftover static demo text ("Koffi Alain",
  "1,284", etc.) remains anywhere on the page.
- `http://127.0.0.1:8000/vendeurs/` and `http://127.0.0.1:8000/annonces-a-valider/` — same
  sidebar/topbar/mobile-nav as the dashboard, correct `active_nav` highlight, existing
  Activer/Suspendre/Valider/Refuser actions still work.

**Note:** as with the previous plan, no browser/screenshot tool is available in this
session — this step is a manual check to run by hand (or hand off to a `run` skill/
browser tool if one becomes available).

- [ ] **Step 4: Stop the dev server**

# Publication d'une annonce véhicule (côté admin) — Design

Date : 2026-08-26
Statut : approuvé, prêt pour plan d'implémentation

## Contexte

Le projet `core/` (Django) a un portail admin fonctionnel : connexion (`/connexion/`), dashboard (`/tableau-de-bord/`), auth réelle avec superadmin. Aucun modèle métier n'existe encore — le dashboard affiche des chiffres statiques (`analyse_et_taches_djona.md`, section D).

Cette fonctionnalité couvre la création d'une fiche véhicule (« annonce ») par un membre du staff Djona depuis le portail admin. Il n'existe pas encore de site/espace vendeur public ; c'est hors périmètre ici.

Le plan d'origine du projet (`plan_d_organisation_djona.md`) mentionnait un parcours « Déposer une annonce » côté vendeur (desktop + 4 écrans mobile), mais aucune maquette n'a jamais été livrée dans le dépôt pour cet écran — ce design part donc de zéro, recentré sur le besoin admin actuel.

### Architecture à deux back-offices

`core/` est **exclusivement réservé aux administrateurs Djona**. Un second back-office, dédié aux vendeurs, sera construit séparément plus tard ; le seul point commun entre les deux sera **la base de données**. Concrètement, il s'agira très probablement de deux projets Django distincts (deux codebases, deux `settings.py`), pointant sur la même base.

Conséquences pour ce design :
- Aucune route, vue ou template vendeur n'est ajoutée ici — confirmé, cohérent avec le périmètre déjà défini plus haut.
- Les modèles `Vendeur`/`Annonce`/`AnnoncePhoto` restent de simples modèles de données, sans aucune logique couplée au portail admin (pas de champ ou de méthode qui présupposerait que seul l'admin y touche).
- Comme les deux projets ne partageront pas de code Python, `core/` sera pour l'instant le seul à posséder des migrations Django pour ces tables (c'est lui qui crée le schéma). Le futur projet vendeur devra soit dupliquer des modèles équivalents en `managed = False` pointant vers les mêmes tables, soit être conçu autour d'un package de modèles partagé — ce choix se fera au moment de construire ce second projet, pas maintenant.
- Pour limiter la friction future, les tables reçoivent un `db_table` explicite (plutôt que le nom auto-généré `annonces_annonce`, qui dépend du nom de l'app Django et serait fragile si le futur projet vendeur ne nomme pas son app pareil).

## Décisions validées

- **Acteur** : le staff Djona crée/gère les fiches véhicules depuis le dashboard admin (pas de flux vendeur public pour l'instant).
- **Structure du formulaire** : wizard visuel en 4 étapes, implémenté comme **un formulaire unique** avec navigation JS entre blocs (Option A — voir « Alternatives écartées »).
- **Vendeur** : modèle `Vendeur` minimal et dédié (pas juste un champ texte), réutilisable plus tard si un espace vendeur est construit.
- **Photos** : Pillow est réintroduit dans `requirements.txt` (avait été retiré) pour utiliser un vrai `ImageField` avec validation d'image.
- **Workflow de statut** : `brouillon → en_attente → publiée/refusée`, cohérent avec le widget « Validation en attente » déjà présent sur le dashboard.
- **Périmètre** : uniquement le modèle de données + le wizard de création/édition. La liste complète des annonces et les actions Valider/Refuser du widget dashboard (actuellement des boutons inertes) restent pour une itération séparée.

## 1. Modèle de données

Nouvelle app Django `annonces`, ajoutée à `LOCAL_APPS` dans `core/settings.py`, séparée de l'app `app` existante — conforme à `core/ARCHITECTURE.md` (« chaque app métier est ajoutée séparément »).

### `Vendeur`

| Champ | Type | Notes |
|---|---|---|
| `nom` | `CharField(max_length=150)` | requis |
| `telephone` | `CharField(max_length=30)` | requis |
| `email` | `EmailField` | optionnel |
| `type` | `CharField` avec `choices` | `particulier` / `professionnel`, défaut `particulier` |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

`Meta.db_table = 'vendeurs'` (nom de table explicite et stable, indépendant du nom de l'app — voir « Architecture à deux back-offices » ci-dessus).

### `Annonce`

Hérite de l'abstract model `Convention` déjà défini dans `app/models.py` (`created_at`, `update_at`, `publish`).

| Champ | Type | Notes |
|---|---|---|
| `vendeur` | `ForeignKey(Vendeur, on_delete=models.PROTECT)` | requis |
| `marque` | `CharField(max_length=80)` | requis |
| `modele` | `CharField(max_length=80)` | requis |
| `annee` | `PositiveIntegerField` | requis |
| `prix` | `PositiveIntegerField` | montant en CFA, pas de décimales |
| `kilometrage` | `PositiveIntegerField` | requis |
| `carburant` | `CharField` avec `choices` | `essence` / `diesel` / `hybride` / `electrique` |
| `boite_vitesses` | `CharField` avec `choices` | `manuelle` / `automatique` |
| `couleur` | `CharField(max_length=50)` | requis |
| `description` | `TextField` | requis |
| `statut` | `CharField` avec `choices` | `brouillon` / `en_attente` / `publiee` / `refusee`, défaut `brouillon` |

`on_delete=models.PROTECT` sur `vendeur` : on ne veut pas qu'une suppression accidentelle de vendeur efface silencieusement ses annonces.

`Meta.db_table = 'annonces'`.

`Annonce.save()` est surchargée pour synchroniser le champ hérité `publish` :

```python
def save(self, *args, **kwargs):
    self.publish = self.statut == self.Statut.PUBLIEE
    super().save(*args, **kwargs)
```

Ceci maintient le contrat `Convention.publish` (utilisé potentiellement ailleurs, ex. Jazzmin) sans dupliquer la logique de statut.

### `AnnoncePhoto`

| Champ | Type | Notes |
|---|---|---|
| `annonce` | `ForeignKey(Annonce, on_delete=models.CASCADE, related_name='photos')` | |
| `image` | `ImageField(upload_to='annonces/%Y/%m/')` | |
| `ordre` | `PositiveIntegerField(default=0)` | ordre d'affichage, déduit de l'ordre d'upload |

Maximum 8 photos par annonce — appliqué côté formulaire (`AnnonceForm.clean()`), pas de contrainte DB.

`Meta.db_table = 'annonce_photos'`.

### Dépendances

`requirements.txt` : réajouter `pillow==10.3.0` (nécessaire pour `ImageField`).

## 2. Formulaire

**`AnnonceForm`** (`ModelForm` sur `Annonce`) couvre tous les champs véhicule listés ci-dessus, plus la gestion du vendeur :

- Champ `vendeur_existant` (`ModelChoiceField(Vendeur, required=False)`) — select des vendeurs existants.
- Champs `nouveau_vendeur_nom`, `nouveau_vendeur_telephone`, `nouveau_vendeur_email`, `nouveau_vendeur_type` (tous `required=False` au niveau champ).
- `clean()` impose : soit `vendeur_existant` est renseigné, soit `nouveau_vendeur_nom` + `nouveau_vendeur_telephone` le sont (erreur de formulaire sinon). Si les deux voies sont renseignées en même temps, `vendeur_existant` a priorité et les champs « nouveau vendeur » sont ignorés.
- La vue crée le `Vendeur` (si voie « nouveau ») avant de sauvegarder l'`Annonce`.

**Photos** : pas de formset. Champ HTML natif `<input type="file" name="photos" multiple accept="image/*">`, traité dans la vue via `request.FILES.getlist('photos')`. Validation du nombre (≤ 8) faite dans `AnnonceForm.clean()` en inspectant `self.files.getlist('photos')` transmis explicitement à la validation du formulaire par la vue (voir plus bas).

## 3. Vue et URLs

**`AnnonceCreateView`** (dans `annonces/views.py`), basée sur `LoginRequiredMixin` + `UserPassesTestMixin` (même pattern que `AdminDashboardView` dans `app/views.py`, `test_func` vérifie `request.user.is_staff`, `login_url = 'connexion_admin'`).

- `GET` : affiche `AnnonceForm()` vide.
- `POST` : instancie `AnnonceForm(request.POST, request.FILES)` (le formulaire a donc accès à `request.FILES.getlist('photos')` dans son `clean()` pour la limite de 8). Deux boutons de soumission distingués par leur `name`/`value` :
  - `<button type="submit" name="action" value="brouillon">Enregistrer comme brouillon</button>`
  - `<button type="submit" name="action" value="soumettre">Soumettre pour validation</button>`
  - La vue lit `request.POST.get('action')` pour fixer `annonce.statut` (`brouillon` ou `en_attente`) avant le `save()` final.
- À la validation réussie : crée le `Vendeur` si nécessaire, sauvegarde l'`Annonce`, boucle sur `request.FILES.getlist('photos')` pour créer les `AnnoncePhoto` (avec `ordre` = index dans la liste), puis redirige vers le dashboard (`dashboard_admin`) avec un message de succès (`django.contrib.messages`).
- En cas d'erreur de validation : réaffiche le template avec le formulaire lié (`AnnonceForm(request.POST, request.FILES)`), erreurs incluses.

**URLs** (`annonces/urls.py`, inclus dans `core/urls.py`) :

```python
urlpatterns = [
    path('annonces/creer/', views.AnnonceCreateView.as_view(), name='annonce_creer'),
]
```

## 4. Template et wizard (Option A)

`templates/annonces/annonce_form.html`, étend `app/base/base.html`, reprend la coquille visuelle du dashboard (sidebar + topbar desktop / header + nav basse mobile — copie du pattern déjà en place dans `dashboard_admin.html`, avec la même config Tailwind/tokens de taille de texte que sur les deux autres pages admin).

**Structure des 4 blocs** (tous dans le même `<form>`, un seul POST) :

1. **Infos générales** : `marque`, `modele`, `annee`, `prix`
2. **Caractéristiques** : `kilometrage`, `carburant`, `boite_vitesses`, `couleur`
3. **Photos** : input multi-fichiers + grille de miniatures générée en JS (`URL.createObjectURL`), bouton de suppression par miniature avant envoi, compteur « x/8 »
4. **Publication** : bascule « vendeur existant / nouveau vendeur », `description`, puis les deux boutons de soumission (brouillon / soumettre)

**Navigation** : indicateur d'étapes en haut (① Infos ─ ② Caractéristiques ─ ③ Photos ─ ④ Publication, étape courante mise en évidence). Chaque bloc est un `<div data-step="1">` à `data-step="4"`, un seul visible à la fois (`hidden` Tailwind). Boutons Précédent/Suivant : le clic sur Suivant appelle `reportValidity()` sur les champs du bloc courant (bloque l'avancée si un champ requis est vide/invalide) avant de basculer au bloc suivant.

**Ré-affichage après erreur serveur** : script inline qui, au chargement, cherche le premier élément portant une erreur Django (`.errorlist`, ou une classe dédiée ajoutée aux champs en erreur) et affiche le `data-step` correspondant au lieu de l'étape 1 par défaut.

**Point d'entrée** : dans `dashboard_admin.html`, remplacer un des liens `href="#"` de la sidebar (et de la nav basse mobile) — le plus logique étant de garder « Validation Queue » tel quel pour plus tard, et d'ajouter un nouveau lien « Nouvelle annonce » (icône `add_circle`) pointant vers `{% url 'annonce_creer' %}`, positionné en haut de la nav (avant Dashboard) pour bien le distinguer des liens encore inertes.

## 5. Erreurs et validations attendues

| Cas | Comportement |
|---|---|
| Champ véhicule requis manquant | Bloqué côté JS à l'étape concernée (`reportValidity`) ; re-vérifié côté serveur (erreurs Django standard si contournement JS) |
| Ni vendeur existant ni nouveau vendeur renseigné | Erreur de formulaire (non-field error), remontée à l'étape 4 |
| Plus de 8 photos sélectionnées | Erreur de formulaire ; JS empêche aussi l'ajout au-delà de 8 dans la grille de miniatures |
| Utilisateur non connecté | Redirigé vers `/connexion/?next=/annonces/creer/` |
| Utilisateur connecté mais non staff | Redirigé vers `/connexion/` (même comportement que le dashboard) |

## 6. Tests

- **Modèles** (`annonces/tests/test_models.py`) : création `Vendeur`, création `Annonce` liée, `save()` synchronise `publish` avec `statut` dans les deux sens (passer à `publiee` → `publish=True`, repasser à `refusee` → `publish=False`).
- **Formulaire** (`test_forms.py`) : rejet si champ véhicule requis manquant ; rejet si ni vendeur existant ni nouveau vendeur ; acceptation avec vendeur existant ; acceptation avec nouveau vendeur (vérifie la création du `Vendeur`) ; rejet si plus de 8 fichiers photo.
- **Vue** (`test_views.py`) : redirection si anonyme ; redirection si non-staff ; POST valide avec `action=brouillon` → `statut == 'brouillon'` ; POST valide avec `action=soumettre` → `statut == 'en_attente'` ; les `AnnoncePhoto` créées correspondent aux fichiers envoyés, dans l'ordre.

## Alternatives écartées

- **`django-formtools` (`SessionWizardView`)** : solution standard pour les wizards Django, mais ajoute une dépendance et une complexité (stockage temporaire des fichiers entre étapes) disproportionnée pour un formulaire à 4 blocs sur une seule page. Écartée au profit de la cohérence avec le style « JS léger, pas de framework » déjà utilisé sur `connexion_admin.html`/`dashboard_admin.html`.
- **Wizard multi-requêtes maison (une URL par étape + session Django)** : offre une vraie navigation par URL et un bouton retour navigateur fonctionnel, mais demande de gérer à la main la validation partielle, le nettoyage de session, et la persistance des fichiers uploadés avant la sauvegarde finale — complexité non justifiée ici.
- **Formulaire simple sur une seule page (sans wizard)** : plus rapide à construire mais explicitement écarté par l'utilisateur au profit d'une UX guidée en étapes.

## Hors périmètre (explicitement)

- Espace/back-office vendeur (projet Django séparé, à construire plus tard — voir « Architecture à deux back-offices »).
- Page de liste des annonces.
- Actions Valider/Refuser du widget « Validation en attente » sur le dashboard (restent des boutons inertes après cette itération).
- Édition d'une annonce existante (cette itération couvre la **création** ; l'édition pourra réutiliser `AnnonceForm` telle quelle dans une itération ultérieure, mais la vue/URL d'édition n'est pas construite ici).
- Redimensionnement/compression des images uploadées (Pillow est utilisé uniquement pour la validation `ImageField`, pas de traitement d'image).

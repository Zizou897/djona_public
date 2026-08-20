# Tâches À Faire & Backlog — Djona

> Ce document liste l'ensemble des tâches restant à accomplir, découpées par priorité : les éléments à finaliser dans le **Parcours Public** actuel (`djona_public`), suivis des **Parcours Produits Futurs** (Compte, Vendeur, Transaction, Admin).

---

## 1. Périmètre Public Immédiat (`djona_public`)

### 🚗 **1.1. Module Comparateur de Véhicules (`/comparer/`)**
- [ ] Créer la vue `vehicle_compare` dans `apps/catalog/views.py`.
- [ ] Ajouter les routes et actions HTMX d'ajout/retrait d'un véhicule du comparateur (`/vehicules/comparer/ajouter/<id>/`, `/vehicules/comparer/retirer/<id>/`).
- [ ] Développer le template [catalog/compare.html](file:///c:/Users/HP/Documents/Github/djona_public/templates/catalog/compare.html) responsive.
- [ ] Intégrer les rationales d'experts, badges "Choix de l'expert" et tooltips explicatifs.

### ❤️ **1.2. Module Favoris — Vue Dédiée (`/favoris/`) [Terminé]**
- [x] Créer la vue `vehicle_favorites` dans `apps/catalog/views.py`.
- [x] Développer le template [catalog/favorites.html](file:///c:/Users/HP/Documents/Github/djona_public/templates/catalog/favorites.html) responsive (basé sur `mes_favoris_djona_mobile`).
- [x] Implémenter le retrait dynamique d'un favori avec effet HTMX `hx-swap="outerHTML swap:300ms"`.

### 🧪 **1.3. Assurance Qualité & Tests**
- [ ] **Tests Unitaires & d'Intégration Django** :
  - Tests des modèles (`Vehicle`, `VehicleImage`, `Favorite`, génération du `slug`).
  - Tests des vues du catalogue (filtrage par marque/prix, tri, pagination, réponses HTMX vs HTML standard).
  - Tests de la gestion des sessions anonymes pour les favoris et le comparateur.
- [ ] **Audit d'Accessibilité (a11y)** :
  - Vérification des contrastes de couleurs (texte sur fond orange/navy).
  - Ajout des attributs `aria-label` et `aria-expanded` sur les boutons d'icônes et menus mobiles.
- [ ] **Performance & Optimisations** :
  - Migration des images vers le format WebP avec gestion du lazy-loading (`loading="lazy"`).
  - Test de montée en charge et vérification des requêtes SQL (prévention du problème N+1 avec `select_related` / `prefetch_related`).

---

## 2. Parcours Produits Futurs (Roadmap Globale)

Le produit final Djona comporte 5 parcours clés. Une fois le parcours public achevé, les modules suivants seront intégrés :

### 👤 **2.1. Parcours Utilisateur & Authentification**
- [ ] Inscription, connexion, réinitialisation de mot de passe (Django Auth / Allauth).
- [ ] Espace Profil Utilisateur (informations personnelles, préférences).
- [ ] Tableau de bord Acheteur (suivi des demandes, historique des recherches, véhicules sauvegardés).

### 🏷️ **2.2. Parcours Vendeur (Tunnel de Dépôt d'Annonce)**
- [ ] **Formulaire de dépôt d'annonce en 4 étapes** :
  1. Informations et identification du véhicule.
  2. Importer des photos haute définition.
  3. Définition du prix, de l'état et des options.
  4. Récapitulatif et soumission à la modération.
- [ ] Espace Vendeur : gestion des annonces actives/en attente, statistiques de consultations et leads.
- [ ] Vitrine Vendeur Professionnel (concessionnaires partenaires).

### 💳 **2.3. Parcours Communication & Transaction (Tunnel « Acheter via Djona »)**
- [ ] **Messagerie sécurisée intégrée** acheteur-vendeur / conseiller Djona.
- [ ] **Système de Compte Séquestre** :
  - Réservation du véhicule et dépôt d'acompte sécurisé.
  - Déblocage des fonds uniquement après validation de l'essai et conformité des papiers.
- [ ] **Suivi de Transaction en temps réel** (Jalons : Inspection -> Offre -> Séquestre -> Essai -> Transfert carte grise).

### 🛡️ **2.4. Parcours Back-office / Administration (Staff Djona)**
- [ ] Interface de modération des annonces soumises par les vendeurs.
- [ ] Saisie des rapports d'inspection technique (150 points de contrôle).
- [ ] Gestion des litiges, validation des déblocages de compte séquestre et tableau de bord des KPIs.

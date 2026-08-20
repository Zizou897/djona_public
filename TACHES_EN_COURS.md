# Tâches En Cours — Djona (Parcours Public)

> Ce document récapitule les fonctionnalités et modules actuellement en cours de développement, d'intégration ou d'optimisation.

---

## 1. Module Favoris — Page Dédiée (`/favoris/`)

- [x] **Backend & Modèle** : Modèle `Favorite` créé avec gestion des sessions anonymes et utilisateurs connectés, API HTMX de basculement (`toggle_favorite`) active sur les cartes du catalogue et de la page détail.
- [x] **Interface Dédiée (Terminée)** :
  - [x] Création des routes `/favoris/` et `/vehicules/favoris/` (`catalog:favorites`).
  - [x] Développement de la vue `vehicle_favorites` dans `apps/catalog/views.py`.
  - [x] Intégration du template responsive `templates/catalog/favorites.html` basé sur la maquette mobile `_mockups/01_public/mobile/mes_favoris_djona_mobile`.
  - [x] Animation de suppression dynamique d'une carte véhicule de la liste des favoris via `hx-target` et HTMX swap sans rechargement.


---

## 2. Consolidation & Développement du Comparateur de Véhicules (`/comparer/`)

- [x] **Analyse des Maquettes** : Étude et synthèse des 5 variantes exploratoires de comparaison issues des maquettes :
  - `comparaison_de_v_hicules_djona`
  - `comparaison_de_v_hicules_avec_badges_djona`
  - `comparaison_de_v_hicules_avec_choix_de_l_expert_djona`
  - `comparaison_de_v_hicules_avec_rationale_expert_djona`
  - `comparaison_de_v_hicules_avec_tooltips_djona`
- [x] **Implémentation de la Vue Unique (Terminée)** :
  - [x] Définition du mécanisme de sélection des véhicules à comparer (mémorisation jusqu'à 3 véhicules dans la session HTTP, bascule HTMX).
  - [x] Création des routes `/vehicules/comparer/` et `/vehicules/comparer/toggle/<id>/` (`catalog:compare`).
  - [x] Développement du template responsive `templates/catalog/compare.html` fusionnant le meilleur des 5 maquettes :
    - Grille comparative côte à côte avec scroll horizontal mobile.
    - Badge dynamique "Choix de l'expert" calculé selon un score composite.
    - Tooltips explicatifs sur tous les critères techniques.
    - Boutons d'action "Acheter via Djona" et purge de la sélection.

---

## 3. Finition & Polissage de l'Expérience Utilisateur (UI/UX)

- [ ] **Micro-Interactions HTMX & Feedbacks** :
  - Ajout d'indicateurs de chargement (spinners HTMX `htmx-indicator`) lors du filtrage du catalogue pour un retour visuel instantané.
  - Gestion des états vides (aucun résultat trouvé pour une recherche/filtrage) avec suggestion de réinitialisation des filtres.
- [ ] **Validation des formulaires côté client & serveur** :
  - Amélioration des retours visuels sur le formulaire de contact.

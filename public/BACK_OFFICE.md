# Back-office Djona — besoins fonctionnels et données

## 1. Objectif

Le back-office est l'outil interne utilisé par les équipes Djona pour opérer la marketplace : modérer les annonces, vérifier les véhicules, accompagner les acheteurs et vendeurs, suivre les transactions et piloter l'activité.

Il doit partager la même base de données que le parcours public Django. Le back-office ne doit donc pas maintenir une copie des véhicules, des utilisateurs ou des transactions. Il doit lire et modifier les mêmes objets métier, avec des droits d'accès stricts et un historique de chaque action sensible.

Ce document distingue :

- l'existant réellement disponible dans le dépôt ;
- les données à ajouter pour couvrir le métier ;
- les écrans et workflows attendus côté staff ;
- les règles de sécurité, d'intégrité et de reporting.

## 2. État actuel de la base partagée

### Données déjà disponibles

| Objet | Données actuelles | Exploitation back-office |
|---|---|---|
| `User` Django | Compte, mot de passe, groupes, permissions, statut actif/superuser | Base des comptes staff et futurs acheteurs/vendeurs |
| `Vehicle` | Marque, modèle, année, prix, kilométrage, carburant, transmission, ville, état, slug, description, publication, vérification, dates | Liste des annonces publiées ou non, recherche et modération initiale |
| `VehicleImage` | Image, véhicule parent, ordre | Contrôle des photos et de l'image principale |
| `Favorite` | Véhicule, utilisateur éventuel, session anonyme, date | Statistiques d'intérêt, sans constituer un lead fiable pour les visiteurs anonymes |
| Sessions Django | Comparateur et favoris anonymes selon le parcours public | Données techniques temporaires, non adaptées au suivi client |

### Limites actuelles à connaître

- `Vehicle.publish` est un booléen : il ne permet pas de distinguer brouillon, soumis, en révision, rejeté, archivé ou vendu.
- `Vehicle.is_verified` ne conserve ni l'inspecteur, ni la date, ni le rapport, ni les résultats des 150 contrôles.
- Un véhicule n'est pas relié à un vendeur ou à un propriétaire métier.
- Les favoris connectés sont prévus par le modèle, mais le parcours public utilise actuellement principalement la session anonyme.
- Aucun modèle ne persiste les demandes de contact, conversations, leads, offres, réservations ou transactions.
- Aucun modèle ne trace qui a publié, vérifié, rejeté, modifié ou archivé une annonce.
- Les statistiques affichées sur l'accueil sont des constantes de démonstration et ne sont pas des KPIs calculés depuis la BD.
- `/admin/` est l'admin technique Django existant, pas encore un espace métier complet.

## 3. Modules du back-office

### 3.1 Tableau de bord opérationnel

La page d'accueil staff doit afficher, selon les permissions :

- annonces à modérer, en attente depuis leur date de soumission ;
- annonces publiées, suspendues, expirées et vendues ;
- inspections à planifier, en cours ou à valider ;
- nouveaux vendeurs à vérifier ;
- demandes de contact et leads non traités ;
- transactions par étape et actions urgentes ;
- litiges ouverts, SLA dépassés et dernière activité ;
- chiffre d'affaires, volume de transactions, panier moyen et taux de conversion sur une période ;
- journal des dernières actions staff.

Les chiffres doivent être calculés à partir d'objets persistés, horodatés et filtrables par période, ville, vendeur et statut. Une métrique doit indiquer sa définition et sa source pour éviter les interprétations divergentes.

### 3.2 Gestion des annonces

Le staff doit pouvoir :

- rechercher par identifiant, vendeur, marque, modèle, ville, statut et date ;
- consulter l'historique complet de l'annonce ;
- corriger les champs avec conservation de la valeur précédente ;
- demander une modification au vendeur ;
- approuver, rejeter, suspendre, dépublier, archiver ou marquer comme vendu ;
- justifier tout rejet, blocage ou modification éditoriale ;
- contrôler les doublons et les prix manifestement incohérents ;
- contrôler les documents et photos requis avant publication ;
- définir la mise en avant éventuelle sans contourner la modération.

Le booléen `publish` peut rester un champ de compatibilité pour le parcours public, mais la source métier doit devenir un statut d'annonce explicite. Le parcours public ne doit afficher que les annonces au statut `published` et répondant aux contrôles de visibilité.

### 3.3 Gestion des vendeurs

Données à gérer :

- identité, téléphone, email et adresse ;
- type : particulier, professionnel ou concessionnaire ;
- informations légales et pièces justificatives ;
- statut KYC/KYB : non commencé, en revue, validé, rejeté, expiré ;
- compte de paiement et coordonnées de reversement, stockés de façon sécurisée ou chez le prestataire de paiement ;
- annonces, leads, transactions, taux de réponse et historique de conformité ;
- notes internes et responsable de compte.

Actions : valider ou refuser un vendeur, suspendre son compte, demander une pièce, réassigner son portefeuille et consulter son activité.

### 3.4 Inspection technique

Le back-office doit permettre de planifier et de saisir une inspection standardisée sur 150 points :

- véhicule inspecté, inspecteur, lieu, date de début et date de clôture ;
- état de chaque point : conforme, défaut mineur, défaut majeur, non contrôlé ;
- commentaire et photo justificative par point si nécessaire ;
- kilométrage relevé et vérification de cohérence ;
- contrôle carrosserie, mécanique, sécurité, intérieur, documents et essai ;
- score global, recommandations et décision : validé, à corriger, non validé ;
- signature ou validation de l'inspecteur ;
- date d'expiration du rapport si une nouvelle inspection est requise.

`is_verified` sur `Vehicle` doit être une conséquence contrôlée d'un rapport validé, et non une case isolée modifiable sans justification.

### 3.5 Acheteurs, leads et support

Le staff doit pouvoir retrouver un acheteur et voir :

- profil et consentements ;
- favoris connectés et recherches sauvegardées ;
- véhicules consultés ou demandés ;
- demandes de contact, rendez-vous et essais ;
- conversations et tickets support ;
- offres, réservations et transactions ;
- incidents, remboursements et litiges.

Le formulaire de contact public doit créer un objet persistant (`SupportTicket` ou `Lead`). Il doit conserver le motif, le message, les coordonnées fournies, la date, la source, le consentement, le statut, l'agent assigné et les réponses.

### 3.6 Messagerie

La messagerie doit être liée à un contexte métier : véhicule, annonce, lead, rendez-vous ou transaction. Elle doit gérer :

- participants et rôle de chaque participant ;
- messages horodatés, pièces jointes et statut lu/non lu ;
- archivage sans suppression destructive ;
- signalement et modération ;
- accès staff selon le rôle et le besoin d'en connaître ;
- journal des actions de consultation ou d'intervention sur une conversation sensible.

Les secrets de paiement, mots de passe et données bancaires ne doivent jamais être écrits dans les messages ou les notes internes.

### 3.7 Transactions « Acheter via Djona »

Le dossier transaction doit suivre au minimum les étapes suivantes :

1. intention ou demande d'achat ;
2. offre et acceptation ;
3. réservation ;
4. inspection et vérification documentaire ;
5. dépôt en séquestre ;
6. essai ;
7. confirmation de conformité ou ouverture d'un litige ;
8. transfert de propriété ;
9. déblocage ou remboursement ;
10. clôture et archivage.

Chaque transition doit enregistrer l'acteur, la date, l'ancien statut, le nouveau statut, la justification et la référence du prestataire externe si applicable.

Le back-office doit permettre de :

- consulter le montant, les frais, la devise et les parties ;
- vérifier les conditions avant passage à l'étape suivante ;
- demander une pièce ou bloquer temporairement le dossier ;
- déclencher un remboursement ou un déblocage uniquement avec une permission dédiée et une double validation pour les montants importants ;
- rapprocher les événements du prestataire de paiement sans stocker les données de carte ;
- exporter un relevé financier auditable.

### 3.8 Litiges et conformité

Un litige doit contenir :

- transaction et parties concernées ;
- catégorie, description, priorité et niveau de risque ;
- preuves, pièces jointes et événements associés ;
- agent responsable, dates de prise en charge et échéance SLA ;
- décisions, remboursements ou compensations ;
- statut ouvert, en analyse, en attente, résolu ou clôturé ;
- motif de clôture et validation finale.

Les actions financières et les décisions de conformité doivent être séparées des simples notes de support et conservées dans un journal immuable.

### 3.9 Contenu, référentiels et configuration

Le staff habilité doit gérer sans modifier le code :

- marques, modèles, villes, carburants et transmissions ;
- textes FAQ et contenus institutionnels si leur administration est prévue ;
- règles de frais et paramètres de transaction versionnés ;
- critères et version du formulaire d'inspection ;
- raisons de rejet, catégories de tickets et statuts ;
- pages SEO publiées et dates de mise à jour.

Les changements de paramètres ayant un impact financier ou juridique doivent être soumis à validation et historisés.

## 4. Modèle de données cible minimal

Les noms ci-dessous sont des propositions cohérentes avec Django. Ils peuvent être répartis dans des apps `accounts`, `catalog`, `operations`, `transactions` et `support`.

### Comptes et permissions

- `UserProfile` : téléphone, type d'utilisateur, préférences et données de profil non sensibles.
- `SellerProfile` : type vendeur, statut KYC/KYB, pièces, données légales et responsable.
- `StaffProfile` : équipe, rôle opérationnel, périmètre géographique et statut.
- `Consent` : utilisateur, finalité, version, date, source et retrait éventuel.

### Catalogue et modération

- `Listing` : vendeur, véhicule, statut, dates de soumission/publication/expiration, motif de rejet, visibilité et responsable.
- `Vehicle` : conserver les caractéristiques publiques ; ajouter au besoin VIN/châssis avec accès restreint, statut de disponibilité et identifiants de référence.
- `VehicleImage` : ajouter type d'image, validation, image principale, métadonnées et motif de rejet.
- `ListingReview` : annonce, modérateur, décision, commentaire, ancienne/nouvelle valeur et date.
- `ModerationEvent` : événement de workflow ou d'automatisation, résultat et erreurs.

### Inspection

- `InspectionTemplate` : version et liste des 150 points actifs.
- `InspectionItem` : catégorie, libellé, ordre, obligation et consigne.
- `InspectionReport` : véhicule/annonce, inspecteur, statut, score, dates et décision.
- `InspectionResult` : rapport, point, état, commentaire, photo et mesure relevée.

### Relation client

- `Lead` : acheteur, annonce/véhicule, source, motif, statut, assignation et dates de suivi.
- `Appointment` : participants, véhicule, lieu, date, type et résultat.
- `SupportTicket` : demande, catégorie, priorité, SLA, assignation, statut et résolution.
- `Conversation` et `Message` : participants, contexte, contenu, pièces jointes et historique de lecture.

### Transaction et risque

- `PurchaseIntent` ou `Offer` : acheteur, vendeur, véhicule, montant, expiration et acceptation.
- `Transaction` : parties, véhicule, statuts, montants, frais, références externes et dates.
- `EscrowEvent` : dépôt, autorisation, déblocage, remboursement, montant, prestataire et statut de rapprochement.
- `Document` : type, propriétaire, objet métier, fichier, statut de vérification, expiration et vérificateur.
- `Dispute` : transaction, motif, preuves, responsable, SLA, décision et résolution.

### Audit et notifications

- `AuditLog` : acteur, action, objet, identifiant, avant/après, justification, IP, user-agent et date.
- `Notification` : destinataire, événement, canal, statut d'envoi et date.
- `WebhookEvent` : prestataire, identifiant externe, payload minimal ou référence chiffrée, statut et idempotence.

## 5. Rôles et permissions

Utiliser les groupes et permissions Django, avec des permissions métier explicites. Le statut `is_staff` seul ne suffit pas à autoriser les opérations sensibles.

| Rôle | Accès principal | Actions interdites par défaut |
|---|---|---|
| Administrateur technique | Configuration, utilisateurs, sécurité, migrations opérationnelles | Modifier une transaction sans trace ou contourner les validations métier |
| Responsable opérations | Vue globale, annonces, vendeurs, inspections, tickets | Accès aux secrets de paiement |
| Modérateur annonces | Lire et décider sur les annonces et images | Déblocage financier, modification des comptes ou KYC sensible |
| Inspecteur | Véhicules affectés et rapports d'inspection | Publication directe sans workflow, accès aux paiements |
| Support client | Profils utiles, leads, tickets, messagerie et rendez-vous | Modifier un rapport d'inspection ou déclencher un remboursement |
| Finance | Transactions, séquestre, rapprochement et remboursements | Modifier les caractéristiques d'une annonce ou un rapport technique |
| Conformité / litiges | KYC, documents, litiges et audit | Changer une décision financière sans procédure prévue |
| Lecture seule / analyste | KPIs et exports autorisés, données anonymisées si possible | Toute écriture et accès aux données sensibles non nécessaires |

Prévoir la limitation par objet : un inspecteur ne voit que ses missions, un support ne voit que les dossiers assignés ou nécessaires, et les exports doivent appliquer les mêmes restrictions que l'interface.

## 6. Règles d'intégrité de la base partagée

- Utiliser des choix de statut explicites plutôt que plusieurs booléens contradictoires.
- Ajouter des contraintes d'unicité et de cohérence : une transaction active par véhicule selon la règle métier, une image principale par annonce, montants positifs, dates dans le bon ordre.
- Utiliser des transactions SQL (`transaction.atomic`) pour les changements de statut qui touchent plusieurs objets.
- Rendre les webhooks et callbacks de paiement idempotents.
- Ne jamais supprimer physiquement une transaction, un litige, une inspection validée ou un journal d'audit ; préférer l'archivage et l'anonymisation réglementaire.
- Protéger les documents et médias privés par contrôle d'accès, même si les images publiques restent servies via `MEDIA_URL`.
- Stocker les montants en entier dans la plus petite unité monétaire utile ou en `Decimal`, jamais en flottant.
- Séparer les données publiques du véhicule des données privées vendeur, KYC et transactionnelles.
- Ajouter des index sur statuts, dates, vendeur, ville, véhicule et références externes pour les files opérationnelles et KPIs.
- Définir une politique de conservation et de suppression des données personnelles conforme aux obligations applicables en Côte d'Ivoire.

## 7. Écrans et parcours staff attendus

1. Connexion staff avec MFA recommandé, expiration de session et journalisation.
2. Tableau de bord avec files d'actions et KPIs.
3. File de modération des annonces.
4. Fiche annonce avec véhicule, vendeur, images, documents, inspection et historique.
5. File des inspections et formulaire des 150 points.
6. Fiche vendeur avec KYC, annonces, leads et activité.
7. CRM léger : leads, tickets, conversations et rendez-vous.
8. Fiche transaction avec timeline, documents, paiements et contrôles.
9. File des litiges avec preuves, SLA et décisions.
10. Reporting et exports filtrés.
11. Gestion des utilisateurs, groupes, permissions et sessions.
12. Journal d'audit consultable et exportable par les responsables habilités.

Chaque fiche doit afficher un identifiant stable, le statut courant, le responsable, la dernière activité et l'historique de décisions. Les actions irréversibles doivent demander confirmation et justification.

## 8. Administration technique recommandée

À court terme, l'admin Django peut servir de console de secours pour les modèles simples. Il ne doit pas être l'unique interface de production pour les transactions, le KYC ou les litiges.

À prévoir :

- une app dédiée `backoffice` ou `operations` avec ses propres URLs et templates ;
- des vues protégées par `login_required`, groupes et permissions objet ;
- des formulaires Django validés côté serveur ;
- des actions HTMX uniquement pour les changements réversibles ou explicitement confirmés ;
- des files paginées avec recherche, filtres et tri ;
- des tests de permissions pour chaque rôle ;
- des signaux ou services métier contrôlés, plutôt que des modifications directes dispersées dans les vues ;
- un système d'export asynchrone pour les gros volumes ;
- des logs applicatifs et alertes sur les erreurs de paiement, webhooks et transitions impossibles.

Le parcours public doit consommer les mêmes services et règles que le back-office. Par exemple, publier une annonce depuis l'admin doit déclencher les mêmes contrôles que toute autre publication et rendre immédiatement l'annonce visible selon les règles de catalogue.

## 9. Priorité d'implémentation

### Phase 1 — rendre la modération possible

- Ajouter le profil vendeur et la relation `Vehicle`/`Listing`.
- Remplacer `publish` seul par un statut de workflow compatible avec le public existant.
- Ajouter les motifs de rejet, l'assignation et `AuditLog`.
- Créer la file de modération et la fiche annonce.
- Persister les demandes de contact dans `Lead` ou `SupportTicket`.
- Ajouter les groupes et tests de permissions.

### Phase 2 — rendre l'inspection et le support opérables

- Ajouter les modèles de rapport, points de contrôle et résultats.
- Relier `is_verified` à une inspection validée.
- Ajouter documents, rendez-vous, tickets et messagerie.
- Mettre en place les notifications et les SLA.

### Phase 3 — rendre le tunnel financier opérable

- Ajouter offres, réservations et transactions.
- Intégrer le prestataire de paiement via références et webhooks idempotents.
- Ajouter séquestre, rapprochement, remboursements et double validation.
- Ajouter litiges et timeline complète.

### Phase 4 — pilotage et durcissement

- Construire les KPIs depuis les données métier réelles.
- Ajouter exports, anonymisation, rétention et alertes.
- Ajouter MFA, revue des permissions et tests de sécurité.
- Tester les scénarios de concurrence : deux modérateurs, double paiement, véhicule déjà réservé, webhook rejoué.

## 10. Critères d'acceptation

Le back-office pourra être considéré comme opérationnel lorsque :

- une annonce peut passer de soumise à publiée ou rejetée avec justification et historique ;
- le public ne voit jamais une annonce non publiée, suspendue ou rejetée ;
- un vendeur et ses documents sont identifiables sans exposer les secrets inutiles ;
- une inspection complète est saisissable, validable et consultable ;
- une demande de contact est persistée, assignée et clôturable ;
- chaque rôle ne peut effectuer que ses actions autorisées ;
- toute action sensible est attribuée à un utilisateur et horodatée ;
- un paiement ou webhook rejoué ne crée pas de double opération ;
- une transaction clôturée et un litige restent auditable ;
- les KPIs affichés peuvent être recalculés à partir de la BD ;
- les tests couvrent les permissions, transitions de statut et règles d'intégrité principales.

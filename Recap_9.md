# Récap 9 – Tests unitaires du backend

## Principe
- Un test **unitaire** vérifie une **petite règle isolée** du backend : logique pure, **sans** base de données, réseau, Stripe ni envoi réel d'e-mails.
- **Stripe** et les **e-mails** sont **simulés** : on vérifie que **notre** code réagit correctement.
- **Horloge simulée** obligatoire pour **tous** les tests de délais (10 min de siège, 30 min de session Stripe, 7 jours d'acompte, 48 h de traitement, 1 h de lien de mot de passe…).
- Hors périmètre : tests des **écrans**, tests de **charge**, audit de **sécurité**, tests avec un **vrai Stripe** (même en mode test), tests d'**intégration** avec la base de données.

## Ce qu'on teste (priorité : l'argent)

### Calcul des prix
- Adultes + enfants (**enfant à moitié prix**), activités, suppléments de places.
- Avec et sans promotion.
- Montant fixe plus grand que la commande : **jamais de prix négatif**.
- Montants en **centimes entiers** (pas de nombres à virgule).
- **Arrondi au centime**, la moitié exacte **vers le haut**.

### Promotions
- Pourcentage appliqué à la bonne partie : **séjour**, **activités** ou **total**.
- **Montant fixe** appliqué une seule fois.
- La **meilleure** promotion gagne ; à **égalité**, la **plus récente**.
- Code promo en **minuscules** accepté.
- Dates incluses **jusqu'à minuit** : tester 23 h 59 le dernier jour et 00 h 01 le lendemain.
- Code **expiré**, **déjà utilisé par ce client** ou **épuisé** : refusé avec le bon message.
- Pourcentage **supérieur à 50 %** refusé.

### Échéancier de paiement
- Acompte de **30 %** si le départ est dans **30 jours ou plus** (nouvelle règle : 30 jours pile ➜ acompte), totalité sinon.
- Tester **29**, **30** et **31** jours.

### Remboursements
- Pourcentage appliqué à ce qui a été **réellement payé**.
- Annulation par **l'agence** : **100 %**.
- **Jamais plus que le total encaissé**, même après plusieurs remboursements partiels.
- Annulation pour **non-paiement** : **aucun** remboursement.
- Jours pile (à confirmer) : 30 jours ➜ 100 %, 15 jours ➜ 50 %, 14 jours ➜ 0 %.

### États des commandes
- Impossible de **confirmer** une commande annulée.
- Impossible de **payer** une commande non confirmée.
- Le client ne peut pas **annuler lui-même** une commande confirmée.
- **Motif obligatoire** pour une annulation.
- Toutes les règles de la grille des états.

### Droits d'accès (un test par règle)
- Un client ne voit **pas la commande d'un autre**.
- Un agent ne peut pas **créer de promotion**.
- Seul l'**administrateur** valide un remboursement et **exporte** les statistiques.
- Un visiteur **déconnecté** ne peut pas commander.

### Places
- Un siège ne peut pas être pris **deux fois**.
- Aucune modification **après paiement**, ni pendant un **paiement en cours**.
- Sièges retenus **libérés après 10 minutes**.
- L'**annulation** libère les places.
- Siège **mobilité réduite** refusé si elle n'est pas déclarée.

### Stripe (simulé)
- Paiement enregistré **uniquement** via le **webhook**.
- Même webhook reçu **deux fois** : un seul paiement.
- Webhook avec une **mauvaise signature** : rejeté.
- États « Acompte payé » / « Payé en totalité » corrects.
- Remboursement demandé à Stripe avec le **bon montant**.
- **Double clic** sur « Payer » : pas de double paiement.
- Stripe **indisponible** : la commande reste « À payer ».

### E-mails (simulés)
- Vérifier que l'e-mail a été **demandé** avec le bon contenu (ex. confirmation de commande).
- **Pas** de promotion sans **consentement** ou avec une adresse **non confirmée**.
- **Pas** de rappel de départ pour une commande **annulée**.
- Le **motif interne** d'annulation n'apparaît **jamais** dans le message au client.

### Comptes
- Adresse e-mail **unique**.
- Mot de passe **trop faible** refusé.
- Lien de réinitialisation : expire après **1 h**, utilisable **une seule fois**.
- Compte supprimé **anonymisé** : commandes et avis conservés, sans nom ni coordonnées (RGPD).

### Avis
- **Un seul** avis par commande.
- Pas d'avis **avant la date de retour**.
- **Commentaire obligatoire** si la note est **≤ 2**.
- Modification impossible **après 30 jours**.

### Statistiques
- Montant **annulé** jamais compté dans le montant **confirmé**.
- Période précédente à zéro : **pas de pourcentage infini**.
- Classement des destinations : **au moins 5 avis**.
- Délai de 48 h : le **week-end compte**.

## Organisation
- **Tableau de correspondance** : chaque règle de gestion des récaps ➜ le ou les tests qui la couvrent. Lisible sans connaître la programmation.
- Chaque règle de chaque récap précédent couverte par **au moins un test**.
- **Noms des tests en français**, qui décrivent le comportement (ex. `un_pourcentage_superieur_a_50_est_refuse`).
- **Bogue signalé** : on écrit d'abord un test qui le **reproduit** (il échoue), puis on corrige. Le test reste (**non-régression**).

## Couverture
- Objectif général : **80 %**.
- **100 %** pour les parties critiques : calcul des prix, promotions, remboursements, échéancier, états des commandes, droits d'accès.
- La couverture est un indicateur, pas un but : ce qui compte, ce sont les **règles** vérifiées.

## Exécution
- Lancement **automatique** à chaque modification du code, sur un **serveur d'intégration**.
- Un seul test en échec ➜ modification **refusée**, rien n'est mis en ligne.
- Durée maximale de l'ensemble : **2 minutes**.
- **Rapport** à chaque modification : nombre de tests, réussis, échoués, couverture, avec les tests **par domaine** (comptes, commandes, promotions, paiement, places, avis, e-mails, statistiques).

## Données de test
- **Uniquement fictives**, clairement reconnaissables : « Marie Test », « Jean Exemple ».
- Adresses en **@exemple.test**, jamais de vraies adresses ni de vrais clients.

## Points à confirmer
- Remboursement aux jours pile (30 j ➜ 100 %, 15 j ➜ 50 %, 14 j ➜ 0 %) : à valider avec le comptable.

# Énoncé 2 – Commande de voyage – Agence « Horizons Lointains » (essentiel)

> Existant (v1) : comptes (clients, agents, administrateur) et catalogue (pays, destinations, activités).
> Objectif de la v2 : permettre à un client de passer une commande de voyage.
> Côté client, l'interface parle de **« demande de voyage »** (pas de « commande »).

## Hors périmètre

- Aucun paiement, aucune facture.
- Aucune notification par e-mail.
- Pas de circuits : **une commande = une destination**.
- Pas de modification de commande (le client annule et refait).
- Pas de noms des autres voyageurs.
- Pas d'état « Terminée ».

## Passer une commande

- Réservé à un **client connecté** (un visiteur doit créer un compte).
- Contenu :
  - une **destination** (active uniquement) ;
  - **date de départ** et **date de retour** ;
  - nombre d'**adultes** et nombre d'**enfants** ;
  - **0 à n activités**, uniquement du **pays de la destination** (l'âge minimum est affiché, pas vérifié) ;
  - un champ **remarques** en texte libre.
- Après validation, la demande apparaît tout de suite dans l'espace du client (« En attente »), avec un message du type : « Votre demande a bien été enregistrée, un conseiller vous rappellera sous 48 heures ».
- **Avertissement** non bloquant si le client a déjà une commande « En attente » pour la même destination aux mêmes dates *(à confirmer)*.

## Règles de validation

- Date de retour **après** la date de départ.
- Départ dans le futur, **au moins 7 jours à l'avance** *(à confirmer)*.
- Au moins **1 adulte**, maximum **10 voyageurs** au total.

## Prix estimé

- Calcul : (prix indicatif de la destination + prix des activités) × nombre de voyageurs, **enfants à 50 %**.
- Mention obligatoire : « **estimation, non contractuel** ».
- Prix **figé au moment de la commande** (insensible aux changements de tarif ultérieurs).

## États et droits

| État | Qui peut y passer |
| --- | --- |
| En attente | À la validation par le client |
| Confirmée | Agent ou administrateur, après traitement et rappel du client |
| Annulée | Personnel (agents + admin) *(à confirmer)*, ou le client tant que la commande est « En attente » |

- Annulation par le personnel : **motif obligatoire**.
- Une commande confirmée ne peut être annulée par le client (il doit appeler).
- **Historique** : pour chaque changement d'état, on garde la **date** et **l'agent** qui l'a effectué.

## Consultation

- **Client** : liste de **ses** commandes (destination, dates, état, prix estimé) + détail.
- **Personnel** : liste de **toutes** les commandes, triable par date de commande (plus récentes d'abord).
  - Filtres : état, pays/destination, client, période de départ.
  - Détail complet, avec téléphone et e-mail du client.

## Cas particuliers

- Destination ou activité désactivée : les commandes existantes restent inchangées.
- Une destination désactivée ne peut plus être commandée.
- Suppression du compte client (RGPD) : données personnelles effacées, commandes conservées **anonymisées** pour les statistiques (solution proposée par l'analyste).

## Points à confirmer (demandés par la cliente)

- Délai minimum de 7 jours avant le départ.
- Annulation ouverte à tout le personnel (position actuelle) ou réservée à l'administrateur.
- Avertissement en cas de commande en double.

## Questions ouvertes (non abordées en réunion)

- Le personnel peut-il annuler une commande déjà « Confirmée » ?
- Faut-il un motif quand c'est le client qui annule ?
- Que note l'historique quand c'est le client qui crée ou annule ?
- Le demi-tarif enfant s'applique-t-il aussi aux activités ?
- Les activités désactivées doivent-elles être exclues des nouvelles commandes ?

## Décisions validées (9 octobre 2026)

Réponses aux points à confirmer et aux questions ouvertes ci-dessus :

| Point | Décision |
| --- | --- |
| Délai minimum avant le départ | 7 jours |
| Annulation côté agence | Tout le personnel (agents + administrateur), motif obligatoire |
| Annulation d'une commande « Confirmée » | Possible par le personnel, avec motif |
| Commande en double (même destination, mêmes dates, « En attente ») | Avertissement non bloquant |
| Motif quand le client annule | Facultatif |
| Historique pour une action du client | Date, nouvel état, auteur « Client », motif éventuel |
| Auteur d'une action du personnel | Nom de l'agent conservé tel quel, même si son compte est supprimé ensuite |
| Demi-tarif enfant | S'applique aussi aux activités |
| Activités désactivées | Exclues des nouvelles commandes |
| Destination sans prix indicatif | Commandable ; estimation « prix de la destination sur devis » (activités seules) |
| Destination ou activité déjà commandée | Suppression interdite : on la désactive |
| Définition d'un « enfant » | Sans précision d'âge ; le conseiller vérifie lors du rappel |

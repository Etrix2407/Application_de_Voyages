# Recap 3 – Avis clients – Agence « Horizons Lointains »

> Existant : comptes (clients, agents, administrateur), catalogue (pays, destinations, activités) et commandes (En attente, Confirmée, Annulée).
> Objectif : permettre aux clients de donner leur **avis** sur leurs voyages, et aux futurs clients de les lire avant de choisir une destination.

## Hors périmètre (pour l'instant)

- Pas de signalement d'avis par les autres clients : la modération reste assurée par le personnel.
- Aucune notification par e-mail : le client voit l'état de son avis dans son espace.
- Pas de photos.
- Pas d'état « Terminée » pour les commandes : un voyage terminé se déduit des dates.

## Qui peut laisser un avis

- Uniquement un client qui a une commande **Confirmée** pour la destination **et** dont la **date de retour est dépassée**.
- **Un seul avis par commande** (le même voyage refait une autre année = une autre commande = un autre avis).

## Contenu d'un avis

- L'avis porte sur la **destination** du voyage effectué.
- **Note de 1 à 5 étoiles** : obligatoire.
- **Titre court**.
- **Commentaire** en texte libre, **1000 caractères maximum** *(à confirmer)* :
  - facultatif ;
  - **obligatoire si la note est ≤ 2**.
- Nom affiché par défaut : « Prénom N. ». Le client peut choisir d'être **anonyme** (« Voyageur anonyme »).
- Pas redemandées, mais affichées :
  - la **date du séjour**, reprise de la commande ;
  - la **date de publication**.
- *Souhaitable (facultatif)* : notes sur les **activités réalisées** pendant ce voyage.

## Cycle de vie

| État | Quand |
| --- | --- |
| En attente de validation | À la création, après une correction ou après la modification d'un avis publié |
| Publié | Validé par un membre du personnel |
| Refusé | Refusé par le personnel, ou avis publié masqué par un agent ou l'administrateur |

- Refus ou masquage : **motif obligatoire**, par exemple « langage injurieux », « hors sujet » ou « contient des coordonnées personnelles ». Le client voit que son avis n'est pas publié, avec le motif.
- Le personnel ne **modifie jamais le texte** d'un client : il valide, refuse ou masque.
- Le client peut **modifier** son avis pendant **30 jours**. Ensuite, il est figé.
  - Modifier un avis **refusé** le fait repasser « En attente de validation ».
  - Modifier un avis **publié** le fait repasser « En attente de validation » ; il est **masqué** au public en attendant.
- Le client peut **supprimer** son avis tant qu'il peut encore le modifier.

## Réponse de l'agence

- **Une seule réponse** par avis, écrite par un agent, que celui-ci peut modifier (pas de fil de discussion).
- Affichée sous l'avis, avec le nom de l'agent ou seulement son prénom *(à trancher)*.

## Affichage public (visiteurs et clients)

- **Liste des destinations** : note moyenne et nombre d'avis (ex. « Marrakech ★ 4,6 (23 avis) ») ; sans avis : « **Pas encore d'avis** » (jamais « 0 étoile »).
- **Fiche destination** :
  - **note moyenne** sur 5 et **nombre d'avis** ;
  - liste des avis publiés, les **plus récents d'abord** ;
  - tri : plus récents ou meilleures notes ;
  - filtre : nombre d'étoiles.
- Chaque avis affiche :
  - la note, le titre et le commentaire ;
  - « Prénom N. » (ex. « Julie D. ») ou « Voyageur anonyme » ;
  - la date du séjour (mois et année) et la date de publication ;
  - la réponse de l'agence, si elle existe.
- Seuls les avis **publiés** comptent dans la moyenne (et, logiquement, dans le nombre d'avis).
- *Souhaitable* : sur la page d'accueil, les **5 derniers avis publiés à 5 étoiles**.

## Côté personnel (agents + administrateur)

- **Avis à modérer** : liste triée du plus ancien au plus récent, pour qu'aucun ne reste bloqué.
- **Tous les avis** : filtres par état, destination, pays, note et période.
- **Compteur** sur le tableau de bord (ex. « 5 avis à modérer »).
- Le personnel voit **toujours le vrai client et sa commande**, même pour un avis anonyme.
- *Souhait des conseillers* : voir les **avis négatifs en priorité**, pour réagir vite. La façon de le faire reste à préciser.

## Cas particuliers

- **Destination désactivée** : ses avis restent en base mais ne sont plus visibles ; ils réapparaissent si la destination est réactivée.
- **Compte client supprimé** : ses avis restent, anonymisés (« Voyageur anonyme », sans lien avec lui, nom supprimé), et comptent toujours dans les moyennes.

## Questions ouvertes (non tranchées en réunion)

- Point de départ des 30 jours : création ou première publication de l'avis ?
- Le titre est-il obligatoire ? Quelle longueur maximale ?
- Limite de 1000 caractères : proposée sans certitude (« disons »).
- Motifs de refus : liste prédéfinie ou texte libre ?
- Avis négatifs « en priorité » : tri, filtre ou mise en évidence ? À partir de quelle note ?
- Filtre « période » : date du séjour ou date de l'avis ?
- Réponse de l'agence : nom complet de l'agent ou prénom seul ?
- Réponse de l'agence : possible sur un avis non publié ? Que devient-elle si le client modifie son avis ?
- L'administrateur peut-il aussi répondre aux avis ?
- Notes d'activités (si faites) : même modération, et comptent-elles dans une moyenne par activité ?

# Recap 4 – Promotions – Agence « Horizons Lointains »

> Existant : comptes, catalogue (pays, destinations, activités), commandes (sans paiement, prix estimé figé à la création) et avis clients.
> Objectif : l'application gère les promotions et **calcule la remise automatiquement** ; le client la voit dès qu'il passe sa commande.

## Hors périmètre

- Seulement deux types de remise : pas de « deuxième voyageur gratuit » ni d'autre formule.
- Pour l'instant, aucune notification par e-mail. Une lettre d'information pourrait venir plus tard : garder la porte ouverte.

## Types et portée

- **Type** :
  - **pourcentage** (ex. « -15 % ») ;
  - **montant fixe** (ex. « -100 € »).
- **Portée** (à quoi la promo s'applique) :
  - **tout le catalogue** ;
  - **un ou plusieurs pays** ;
  - **une ou plusieurs destinations**.
- **Assiette** (sur quelle partie du prix) :
  - **séjour** : prix de la destination seulement ;
  - **activités** : prix des activités seulement ;
  - **total** : séjour + activités.

## Calcul de la remise

- Exemple : -10 % « sur le séjour », Lisbonne à 800 €/adulte + une activité à 60 € → la remise porte sur les 800 € seulement, les 60 € ne sont pas touchés.
- **Pourcentage** : proportionnel au montant de l'assiette.
- **Montant fixe** : appliqué **une seule fois par commande**, pas par personne.
- Le prix après remise ne descend **jamais sous 0 €**.

## Validité dans le temps

- **Date de début** et **date de fin** : elles portent sur la **date à laquelle le client passe la commande**, pas sur la date du voyage.
- Le **dernier jour est inclus**, jusqu'à minuit.
- *Optionnel* : une **période de départ** autorisée (ex. départs entre septembre et novembre). Sans période, tous les départs sont acceptés.

## Promotions automatiques et codes promo

- **Automatique** : tout le monde y a droit, dans sa portée (ex. « Semaine du Portugal »).
- **Sur code** (ex. « BIENVENUE15 ») : l'agence le distribue (clients fidèles, réseaux sociaux) et le client le saisit dans sa commande.
- Format d'un code :
  - lettres et chiffres uniquement, sans espaces ;
  - **4 à 20 caractères** ;
  - stocké en majuscules, mais la saisie en minuscules est acceptée ;
  - **unique** : deux promotions n'ont jamais le même code.
- **Un seul code par commande**.
- **Pas de cumul** : le client reçoit la **meilleure** promotion, c'est-à-dire celle qui donne la **plus grande remise en euros**. En cas d'égalité, la **plus récente** l'emporte.

## Limites d'utilisation (optionnelles, tous types)

- **Maximum au total** (ex. 50 commandes) et **maximum par client** (ex. 1). Sans limite indiquée, l'utilisation est illimitée.
- Une utilisation est comptée **à la création** de la commande.
- Si la commande est **annulée**, l'utilisation est **rendue** et le client peut réutiliser la promotion. On ne compte donc que les commandes non annulées.

## Figé dans la commande

- Une modification ou une désactivation de la promotion ne change **rien** aux commandes existantes.
- La commande conserve :
  - la **remise appliquée** ;
  - le **nom de la promotion** ;
  - le **montant économisé**.

## Données d'une promotion

- Nom (ex. « Semaine du Portugal ») et description courte.
- Type et valeur.
- Portée et assiette.
- Dates de validité, et période de départ éventuelle.
- Code éventuel et limites éventuelles.
- État.
- Administrateur qui l'a créée.

## Règles de validation

- Pourcentage entre **1 et 50 %** (50 % maximum).
- Montant fixe **> 0**.
- Date de fin **≥** date de début.

## États et gestion

- États affichés dans la liste : **À venir**, **En cours**, **Terminée** (déduits des dates) ou **Désactivée**.
- **Pas de suppression en principe** : on **désactive**. Une promo désactivée n'est plus proposée mais reste dans l'historique. On peut la désactiver avant sa date de fin, par exemple après une erreur de valeur.
- Exception : une promotion **jamais utilisée** peut être supprimée.
- Une promotion **déjà utilisée** :
  - on peut modifier son nom, sa description et sa date de fin, ou la désactiver ;
  - on ne peut **pas** modifier sa valeur ni sa portée ; pour changer cela, on crée une nouvelle promotion.
- **Historique** : date et auteur de chaque création, modification et désactivation.

## Droits

- **Administrateur uniquement** : créer, modifier, désactiver et (si jamais utilisée) supprimer les promotions.
- **Agents** : consulter seulement, pour renseigner les clients.

## Côté client et public

- **Fiche destination** : un bandeau du type « -15 % jusqu'au 31 mars » si une promotion **automatique** est en cours.
- **Liste des destinations** : une étiquette « **Promo** » sur la carte si une promotion **automatique** est en cours.
- *Souhait* : une page « **Nos offres du moment** » qui liste les promotions automatiques en cours (argument de vente).
- **Formulaire de commande** :
  - un champ « Code promo » ;
  - en cas de succès : « Code appliqué : -100 € » ;
  - en cas d'échec : un message simple, sans jargon technique :
    - « Code invalide » ;
    - « Ce code a expiré » ;
    - « Ce code ne s'applique pas à cette destination » ;
    - « Vous avez déjà utilisé ce code » ;
    - « Ce code n'est plus disponible ».
- **Récapitulatif** : prix avant remise, remise, prix après remise.
- Les promotions **sur code** ne sont **jamais visibles publiquement**, seulement par le personnel.

## Statistiques (une page par promotion)

- Nombre de commandes qui l'ont utilisée.
- **Montant total des remises accordées**.
- Nombre de clients différents.
- Liste des commandes concernées.
- Les commandes **annulées** sont affichées à part et **ne comptent pas** dans le total des remises.

## Questions ouvertes (non tranchées en réunion)

- « -20 % sur les activités gastronomiques » : faut-il pouvoir cibler une **catégorie d'activités** ? Rien dans cette réunion ne définit de catégories, et la portée ne prévoit que pays et destinations.
- Montant fixe supérieur à son assiette (ex. -100 € « sur les activités » pour 60 € d'activités) : remise plafonnée à 60 €, ou 100 € déduits du total ?
- « La plus récente » en cas d'égalité : date de création ou date de début ?
- Code saisi mais promo automatique plus avantageuse : quel message afficher au client ?
- Une promotion déjà utilisée : seuls le nom, la description et la date de fin sont cités comme modifiables. L'assiette, le code, les limites, la date de début et la période de départ sont donc a priori figés, à confirmer.
- Modifier la date de fin : peut-on l'avancer, voire la mettre dans le passé ?
- Remise sur les « activités » alors que la commande n'en contient pas : remise de 0 €, ou promo non applicable ?
- Ordre de calcul avec le demi-tarif enfant (règle du Recap 2) : la remise s'applique-t-elle après le calcul du prix enfants compris ? (C'est la lecture la plus logique.)
- Les statistiques « nombre de commandes » et « clients différents » excluent-elles les commandes annulées, comme le total des remises ?
- Période de départ : faut-il aussi vérifier que sa fin est postérieure à son début ?

# Récap 6 – Statistiques et tableau de bord

## Deux tableaux de bord
- **Opérationnel** pour les **agents** : ce qu'ils ont à faire. Pas de chiffre d'affaires.
- **Pilotage** pour l'**administrateur** : tout.
- Les **clients** ne voient aucune statistique (seulement leurs propres commandes, comme avant).
- Hors périmètre : **affectation** d'une commande à un agent (« qui s'en occupe »).

## Tableau de bord opérationnel (agents)
- Quatre gros chiffres en haut de l'écran :
  - **Commandes en attente** (toutes, pas de portefeuille par agent) ;
  - Commandes en attente depuis **plus de 48 h**, **en rouge** ;
  - **Avis à modérer** ;
  - **Départs de la semaine** : commandes confirmées qui partent dans les **7 prochains jours**.
- Chaque chiffre est **cliquable** et ouvre la liste **filtrée** correspondante.
- Données en **temps réel**.

## Tableau de bord de pilotage (administrateur)

### Période
- Analyse par **date de commande** (par défaut) ou par **date de départ**, au choix.
- Raccourcis : **ce mois-ci**, **le mois dernier**, **ce trimestre**, **cette année**, **les 12 derniers mois**, plus une **période personnalisée** (deux dates).
- **Comparaison** avec la période précédente : « +12 % par rapport au mois dernier ».
  - Vert si c'est bien, rouge si c'est mauvais : le sens **dépend de l'indicateur** (une hausse des annulations est rouge).
  - Période précédente à zéro : « nouveau » ou un tiret, **jamais** « +∞ % ».

### Commandes et montants
- **Nombre de commandes** par état : en attente, confirmées, annulées.
- **Taux de confirmation** et **taux d'annulation**.
- « **Montant estimé des commandes confirmées** » (libellé imposé : ce n'est **pas** de l'argent encaissé), **après remise**.
- **Total des remises accordées**.
- **Montant estimé des commandes annulées** (affiché à part, jamais compté dans le montant confirmé).
- **Potentiel en attente** : montant estimé des commandes en attente.

### Classements
- **Top 5 destinations** et **top 5 pays** par nombre de commandes confirmées, avec le montant estimé.
- **Top 5 activités** les plus choisies.
- **Bas du classement** (moins demandées), uniquement pour les destinations **actives**.

### Graphiques (simples, pas de 3D)
- **Courbe** du nombre de commandes par mois sur 12 mois (saisonnalité).
- **Barres** par pays.
- **Répartition** par état des commandes.

### Promotions
- **Promotions en cours** : nombre d'utilisations et total des remises.
- La promotion qui a **le mieux marché** (le plus de commandes).
- Simple résumé, avec un **lien** vers la page de chaque promotion (Récap 4) : pas de double travail.

### Avis
- **Note moyenne globale** de l'agence et **nombre d'avis publiés** sur la période.
- **3 destinations les mieux notées** et **3 les moins bien notées**, seulement si elles ont **au moins 5 avis**.

### Clients
- **Comptes créés** sur la période, **total de clients inscrits** (comptes actifs seulement), clients ayant **passé au moins une commande**.
- **Taux de conversion** : comptes qui finissent par commander.
- Comptes supprimés (anonymisés) :
  - leurs **commandes** restent dans les totaux ;
  - ils ne comptent plus dans les **clients inscrits** ;
  - « comptes créés » sur une période passée **ne change pas** ➜ conserver la **date de création** de façon anonyme.

### E-mails
- Nombre d'**e-mails en échec** sur les **7 derniers jours**, avec un lien vers le journal.
- Nombre de clients marqués « **adresse à vérifier** ».

### Délai de traitement
- Délai = temps entre la **création** de la commande et sa **confirmation ou annulation**.
- **Moyenne** et **pire cas**.
- **Part des commandes traitées en moins de 48 h** (ex. « 87 % »).
- 48 heures **réelles**, week-end compris (voir points à confirmer).

## Signaux (pas d'e-mail)
- Signaux en couleur sur le tableau de bord quand :
  - le taux d'annulation dépasse **25 %** ;
  - plus de **5** commandes sont en attente depuis plus de 48 h ;
  - le taux de traitement en 48 h passe sous **80 %**.
- **Seuils modifiables** par l'administrateur.

## Fraîcheur des données
- Opérationnel : **temps réel**.
- Pilotage : mise à jour **toutes les heures**, avec la **date et l'heure** de la dernière mise à jour affichées. Ne doit pas ralentir l'application.

## Export
- Réservé à l'**administrateur**, en **Excel ou CSV**.
- Liste des commandes de la période : numéro, date de commande, date de départ, destination, pays, nombre de voyageurs, montant estimé, remise, état.
- **Pas de nom ni de coordonnées** : seulement un **numéro de client** (RGPD).
- Chaque export est **tracé** : qui, quand, quelle période.

## Affichage
- Lisible sur **téléphone** : les gros chiffres d'abord, les graphiques ensuite.

## Points à confirmer
- **Statistiques par agent** (visibles de l'administrateur seulement) : nombre de commandes traitées et délai moyen avant la première action. Si c'est retenu, les agents en sont **informés**.
- Délai de 48 h compté en **heures ouvrables** plutôt qu'en heures réelles (l'agence est fermée le dimanche).

## Souhaitable
- **Carte du monde** colorée selon les pays les plus vendus.

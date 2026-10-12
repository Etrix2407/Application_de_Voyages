# Récap 8 – Choix des places pour les activités avec sièges

## Principe
- Le client choisit lui-même ses **places numérotées**, sur un **plan** (comme un site de spectacles).
- Concerne seulement les activités marquées « **avec places numérotées** » : excursions en car, traversées en ferry, spectacles en salle.
- Les autres activités (souk, balade en dromadaire…) **ne changent pas**.
- Hors périmètre : **cabines** de ferry, **bébés** sur les genoux, remplacement d'une séance annulée **après paiement** (géré par téléphone hors application).

## Séances
- Une activité avec places numérotées a des **séances** : **date**, **heure** et **plan de places** propres (ex. Sintra le 12 mars à 9 h).
- Créées par les **agents**.
- Le client ne voit que les séances **pendant son séjour** (entre départ et retour).
- Séance **complète** : affichée « **Complet** », impossible à choisir ; redevient disponible si des places se libèrent.
- Moins de **10 places** libres : « **Plus que X places** ».
- Séance **annulée** par l'agence (grève, météo) : état « **Annulée** » avec motif.
  - Les commandes concernées **ne sont pas annulées** automatiquement : l'agent reçoit la **liste** des commandes avec les coordonnées pour **appeler** les clients.
  - Places **libérées** dans les commandes **non payées** ; pour les autres, l'agent gère manuellement.
- Séance **passée** : plus de réservation, données conservées.
- Une séance avec des places réservées **ne se supprime pas** : on la **désactive** ou on l'annule.

## Plans de places
- Gérés par l'**administrateur**.
- Un **modèle** (« Car 49 places », « Ferry Lisbonne – pont 1 », « Théâtre Rivoli ») composé de **rangées** et de **sièges** numérotés (ex. 12C).
- Création simple : « 12 rangées, 4 sièges, une allée au milieu », puis clic sur les sièges pour les marquer :
  - **hors service** ;
  - **mobilité réduite** ;
  - changer de **zone**.
- **Zones** (Orchestre, Balcon, Avant du car…) avec un **supplément par place** en euros (0 € possible).
- Plusieurs **niveaux** (ponts du ferry), affichés en **onglets**.
- La séance garde sa **propre copie** du plan : modifier le modèle ne touche que les séances créées **ensuite**.

## Prix
- Supplément de zone **ajouté au prix de l'activité**.
- Il entre dans la partie « **activités** » du prix estimé, donc il compte pour les **promotions sur les activités**.

## Choix des places par le client
- Au moment de **la commande** : activité ➜ « Quelle séance ? » ➜ plan ➜ **une place par voyageur** (adultes et enfants).
- Le plan peut être **consulté** sans être connecté ; la **réservation** demande d'être connecté et se fait pendant la commande.
- Affichage :
  - couleurs **libre**, **déjà pris**, **choisi par moi**, **hors service**, **mobilité réduite**, avec **légende** ;
  - un **symbole ou motif** en plus de la couleur (daltonisme) ;
  - **zoom** au doigt sur téléphone, sièges assez gros ;
  - prix des zones visible, **total des suppléments** mis à jour à chaque clic ;
  - places prises : « **occupé** », jamais le nom d'un autre client.
- **Siège retenu 10 minutes** après le clic, avec un **minuteur**. Passé ce délai, les sièges sont **libérés**.
- Siège pris entre-temps : « Désolé, cette place vient d'être prise, choisissez-en une autre », et le plan se met à jour.
- Plan **rafraîchi automatiquement** toutes les quelques secondes.
- Deux séances qui se **chevauchent** : **avertissement non bloquant**.

## Après validation de la commande
- Les sièges sont **réservés pour la commande** tant qu'elle existe, même « En attente ».
- Séance, date, heure et numéros de places apparaissent dans le **récapitulatif** et les **e-mails**.
- **Annulation** de la commande (par le client, l'agence ou pour non-paiement après 7 jours) : places **libérées**, même sans remboursement.
- Un agent peut **libérer les places** d'une commande abandonnée, mais on préfère passer par l'**annulation**.

## Modification des places
- Exception à « commande non modifiable » : le client peut **changer ses places tant qu'aucun paiement n'a été fait**, même après confirmation.
- Places **bloquées** pendant un **paiement en cours** ; si le paiement échoue ou expire (30 min), elles redeviennent modifiables.
- **Verrouillage définitif** au **premier paiement réussi** (acompte compris) : plus personne ne change, ni le client, ni les agents, ni l'administrateur. Pour changer : annuler (règles de remboursement habituelles) et recommencer.

## Rôle des agents
- Ils peuvent **attribuer les places** à la place du client, **avant paiement** (client au téléphone, oubli).
- **Confirmation impossible** tant que **chaque voyageur** n'a pas de siège pour **chaque** activité à places numérotées.

## Mobilité réduite
- Le client **déclare** la mobilité réduite dans sa commande : case à cocher + **nombre de personnes**.
- Les sièges « mobilité réduite » ne sont proposés **qu'à ces clients**, sinon **grisés**.

## Côté personnel
- Pour chaque séance : le **plan** avec les places occupées ; clic sur une place ➜ la **commande** concernée.
- **Liste des passagers** (pour le guide) par ordre de place : numéro de place, **nom du client** qui a commandé, **téléphone**, mention **mobilité réduite**.
  - **Impression** ou **export PDF**, par les **agents** et l'**administrateur**.

## Volume
- Environ **30 séances** ouvertes en même temps, plans de **20 à 300 places**, pointes le **week-end**.

## Statistiques (plus tard, tableau de bord)
- **Taux de remplissage** par séance, séances **presque complètes**, séances **vides** à départ proche, **total des suppléments** encaissés.

## Points à confirmer
- Le **compagnon** d'une personne à mobilité réduite doit pouvoir s'asseoir **à côté** : comment le gérer ?

## Souhaitable
- Bouton « **Placer ensemble** » : sièges côte à côte, ou les plus proches possible.
- Icônes **fenêtre**, **couloir**, **place avec espace** (information affichée, pas critère de recherche).

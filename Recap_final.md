# Récap final – Agence « Horizons Lointains »

> Synthèse de **tous les récaps (1 à 9)**. Quand deux récaps se contredisent, c'est **le plus récent qui l'emporte** ; la règle remplacée est signalée par ⚠️.
> Les réponses de la cliente notées dans le README (v3, v4, v5) ne sont pas reprises ici.

## Hors périmètre (état actuel)
- **Facturation**, TVA, frais Stripe, versements bancaires (comptable, hors application).
- Version **néerlandaise** : français uniquement.
- **Circuits** : une commande = **une destination**.
- **Noms des autres voyageurs** ; **bébés** sur les genoux ; **cabines** de ferry.
- ⚠️ Modification d'une commande (le client annule et refait, Récap 2), **sauf les places** tant qu'aucun paiement n'est fait (Récap 8, voir § Places) ; modification du **prix après paiement**.
- État « **Terminée** » pour les commandes : un voyage terminé se déduit des dates.
- **Affectation** d'une commande à un agent.
- Signalement d'avis par les clients ; **photos** dans les avis.
- Promotions : uniquement **pourcentage** ou **montant fixe** (pas de « 2e voyageur gratuit »).
- E-mails promotionnels : pas de programmation, ciblage ni statistiques d'ouverture.
- Remplacement d'une **séance annulée après paiement** (géré par téléphone).
- Tests : écrans, charge, audit de sécurité, vrai Stripe, tests d'intégration avec la base.
- ⚠️ Paiement, e-mails et notifications étaient hors périmètre en v1–v4 : ils sont désormais **inclus** (Récaps 5 et 7).

## Utilisateurs et droits
| Rôle | Création du compte | Droits principaux |
|---|---|---|
| Visiteur | – | Consulter le catalogue, les avis publiés, les **plans de places** |
| Client | Auto-inscription | Catalogue ; profil ; supprimer son compte ; commander (adresse **confirmée**) ; payer ; choisir ses places ; donner un avis |
| Agent | Créé par l'administrateur (invitation) | Catalogue et **séances** ; liste des clients (correction sauf mot de passe) ; commandes (confirmer, saisir le prix définitif, annuler, attribuer des places) ; modération des avis et réponse ; consulter les promotions ; tableau de bord **opérationnel** ; proposer un remboursement ; liste des passagers |
| Administrateur (la gérante) | Créé en amont | Droits de l'agent + comptes agents + **promotions** + **plans de places** + **valider les remboursements** + tableau de bord de **pilotage** + **export** + envoi promotionnel + modèles d'e-mails + vérifier un paiement auprès de Stripe |

- Un client ne voit **jamais** les données d'un autre client ni celles du personnel.

## Comptes
- Une adresse e-mail = **un compte**, unique (clients comme agents).
- Mot de passe **robuste**, jamais stocké ni envoyé en clair, récupérable par lien (valable **1 h**, utilisable **une seule fois**).
- **Client** : nom, prénom, e-mail, mot de passe, téléphone, date de naissance.
- **Agent** : nom, prénom, e-mail professionnel, mot de passe, numéro d'employé, rôle.
- Adresse **non confirmée** : connexion et catalogue possibles, mais **pas de commande** ni d'e-mail promotionnel ; les e-mails de service partent.
- **Suppression du compte** (RGPD) : données personnelles effacées ; commandes et avis **conservés anonymisés** (« Voyageur anonyme », sans nom), les avis comptant toujours dans les moyennes ; la **date de création** est gardée de façon anonyme pour les statistiques.

## Catalogue
- Un **pays** contient plusieurs destinations ; une destination appartient à **un seul** pays.
- Une **activité** appartient à un pays (destination précise optionnelle).
- **Pays** : nom, continent, langue, monnaie, description, visa requis pour les Belges, décalage horaire, actif/inactif.
- **Destination** : nom, description, période idéale, prix indicatif « à partir de », photo, pays, actif/inactif.
- **Activité** : nom, description, catégorie (culture, détente, sport, gastronomie, aventure), durée, prix par personne, difficulté, âge minimum, pays, destination optionnelle, actif/inactif, **« avec places numérotées » oui/non**.
- Pas de suppression d'un élément utilisé (pays avec contenu, destination ou activité déjà commandée) : on le **désactive** (il disparaît alors pour les clients).
- Seul le **personnel** modifie le catalogue.
- Consultation : liste des pays, détail d'un pays, recherche par mot, filtres par catégorie et budget.

## Commandes (« demandes de voyage » côté client)

### Passer une commande
- Client **connecté**, adresse **confirmée**.
- Une **destination active**, date de **départ** et de **retour**, nombre d'**adultes** et d'**enfants**, **0 à n activités** du pays (actives ; âge minimum affiché, pas vérifié), **remarques**, **code promo** éventuel, déclaration **mobilité réduite** (case + nombre de personnes), **séance et places** pour chaque activité à places numérotées.
- Message : « Votre demande a bien été enregistrée, un conseiller vous rappellera sous 48 heures ».
- **Avertissement non bloquant** : commande « En attente » en double (même destination, mêmes dates) ; deux séances qui se **chevauchent**.

### Validation
- Retour **après** le départ ; départ **au moins 7 jours** à l'avance.
- Au moins **1 adulte**, **10 voyageurs** maximum.

### Prix estimé
- (prix de la destination + prix des activités + **suppléments de places**) × voyageurs, **enfants à 50 %** (activités comprises).
- Destination sans prix : commandable, « prix de la destination **sur devis** ».
- Mention « **estimation, non contractuelle** ».
- **Figé** à la création, remise comprise.
- Montants en **centimes entiers** ; arrondi au centime, la **moitié vers le haut**.

### Prix définitif (Récap 7)
- Saisi par l'**agent à la confirmation** : par défaut le prix estimé **après remise** (promotion **non recalculée**) ; modifiable avec **justification obligatoire**.
- Le client voit l'estimation, le prix définitif et la justification, et peut obtenir une **annulation sans frais avant de payer**. ⚠️ Il ne peut pas l'annuler **lui-même** une fois la commande confirmée (Récaps 2 et 9) : il appelle l'agence (voir Points encore à confirmer).
- **Non modifiable** après le premier paiement.

### États et historique
| État | Qui |
|---|---|
| En attente | À la création par le client |
| Confirmée | Agent ou administrateur, après rappel du client — **impossible** si un voyageur n'a pas de siège pour une activité à places numérotées |
| Annulée | Le client tant que « En attente » (motif facultatif) ; le personnel à tout moment (**motif obligatoire**) ; **automatiquement** si l'acompte (ou la totalité) n'est pas payé dans les 7 jours suivant la confirmation (« paiement non reçu ») |

- Un client **ne peut pas annuler** une commande confirmée : il appelle l'agence.
- Annulation par l'agence : **motif interne** (personnel) + **explication pour le client** (vide ➜ message neutre).
- **Historique** de chaque changement : date, nouvel état, auteur (nom de l'agent conservé, ou « Client »), motif.

### Consultation
- **Client** : ses commandes (destination, dates, état, prix estimé, **prix définitif**, payé, reste à payer, prochaine échéance, places) + détail.
- **Personnel** : toutes les commandes, plus récentes d'abord ; filtres état, pays/destination, client, période de départ ; détail avec coordonnées du client, paiements, remboursements, **lien Stripe** (jamais montré au client).

### Cas particuliers
- Destination ou activité désactivée : commandes existantes inchangées, plus commandable.
- Définition d'un « enfant » : sans âge précis, vérifié par le conseiller.

## Paiement via Stripe (Récap 7, mis à jour par le Récap 9)
- Paiement **après confirmation**, sur la **page sécurisée de Stripe** ; l'application ne voit **jamais** la carte.
- **Carte** (Visa, Mastercard) et **Bancontact**, en **euros** uniquement.
- Bouton « **Payer ma commande** » dans l'espace client ; retour : « Merci, votre paiement est bien enregistré » ou « Paiement non effectué ».

### Échéancier
- ⚠️ Départ dans **30 jours ou plus** (30 jours pile compris, Récap 9) : « **Payer l'acompte (30 %)** » ou « **Payer la totalité** ». Solde au plus tard **30 jours avant le départ**.
- Départ dans **moins de 30 jours** : **totalité** en une fois.
- Acompte : **7 jours** pour payer, rappels à **J+3** et **J+6**, puis **annulation automatique**.
- Solde : rappels à **45**, **35** et **31 jours** du départ ; non payé à 30 jours ➜ le **conseiller est averti** et appelle. **Pas d'annulation automatique**.

### Sécurité
- Session de paiement valable **30 minutes**.
- **Jamais de double paiement** : une seule demande active par commande et par échéance.
- Seul le **webhook** Stripe fait foi (le retour du navigateur, non) ; webhook en double ignoré, mauvaise signature rejetée ; l'administrateur peut **vérifier** un paiement auprès de Stripe.
- Paiement refusé : on peut **recommencer**, sans limite de tentatives.
- Stripe indisponible : « Le paiement est momentanément indisponible, réessayez dans quelques minutes », la commande reste « À payer ».
- Clés **hors du code**, **mode test** et **mode réel** séparés, compte Stripe de l'agence.

### État du paiement (commande confirmée uniquement)
- À payer ➜ Acompte payé ➜ Payé en totalité ; Remboursé partiellement ; Remboursé totalement.
- Un refus n'est pas un état : il va dans le **journal des tentatives**.

### Remboursements
- Annulation par **l'agence** : **100 %**.
- Annulation par le **client** : plus de 30 jours ➜ **100 %** ; de 30 à 15 jours ➜ **50 %** ; moins de 15 jours ➜ **rien**.
- Pourcentage appliqué à ce qui a été **réellement payé**.
- Annulation pour **non-paiement** : rien à rembourser.
- L'application **calcule**, l'agent **propose**, l'**administrateur valide** (montant modifiable avec justification) ; l'application déclenche le remboursement **dans Stripe**.
- Remboursements partiels successifs, **jamais plus que le total encaissé**.
- Message : « sous **5 à 10 jours ouvrables** ».

## Places numérotées (Récap 8)

### Séances et plans
- Activités « avec places numérotées » (car, ferry, spectacle) : des **séances** (date, heure, plan) créées par les **agents**.
- **Plans** créés par l'**administrateur** : modèle de **rangées** et **sièges** numérotés, allées, sièges **hors service** / **mobilité réduite**, **zones** avec **supplément** par place, plusieurs **niveaux** (onglets).
- Création simple (« 12 rangées, 4 sièges, allée au milieu »), puis clic sur les sièges.
- La séance garde **sa copie** du plan : modifier le modèle ne touche que les séances créées ensuite.
- Supplément de zone ajouté à la partie « **activités** » du prix (donc concerné par les promotions sur les activités).
- Séance **complète** : « Complet » ; moins de **10 places** : « Plus que X places ».
- Séance **annulée** : motif ; commandes **non annulées** automatiquement, liste des clients à appeler ; places libérées dans les commandes non payées.
- Séance passée : plus de réservation, données conservées ; séance avec réservations : **désactivée** ou annulée, jamais supprimée.

### Choix par le client
- Seulement les séances **pendant le séjour** ; **une place par voyageur** (adultes et enfants).
- Plan : libre / pris / choisi / hors service / mobilité réduite, **légende**, **symbole en plus de la couleur**, **zoom** sur téléphone, total des suppléments en direct, « occupé » sans nom.
- Siège **retenu 10 minutes** (minuteur), puis libéré ; « Désolé, cette place vient d'être prise » ; plan **rafraîchi automatiquement**.
- Sièges mobilité réduite réservés aux clients qui l'ont **déclarée**, sinon grisés.
- Plan **consultable** sans connexion, réservation pendant la commande.

### Après la commande
- Places réservées tant que la commande existe ; affichées dans le récapitulatif et les e-mails.
- **Modifiables tant qu'aucun paiement** n'a été fait, même après confirmation ; **bloquées** pendant un paiement en cours (de nouveau modifiables s'il échoue ou expire après 30 min) ; **verrouillées définitivement** au premier paiement réussi, acompte compris : plus personne ne les change (client, agents, administrateur) ; pour changer, on annule et on recommence.
- Toute **annulation** de commande libère les places (même sans remboursement).
- L'agent peut **attribuer** les places avant paiement, et **libérer** celles d'une commande abandonnée (l'annulation reste préférée).
- Personnel : pour chaque séance, le **plan** avec les places occupées ; un clic sur une place ouvre la commande.
- **Liste des passagers** (agents et administrateur) : place, nom du client, téléphone, mobilité réduite ; impression ou PDF.

## Avis clients (Récap 3)
- Seulement pour une commande **Confirmée** dont la **date de retour est passée** ; **un avis par commande**.
- Porte sur la **destination** : note **1 à 5** (obligatoire), titre court, commentaire (max **1 000** caractères, **obligatoire si note ≤ 2**).
- Affiché « Prénom N. » ou « Voyageur anonyme », avec date du séjour et date de publication.
- États : **En attente de validation** ➜ **Publié** ou **Refusé** (refus ou masquage avec **motif obligatoire**). Le personnel ne modifie **jamais** le texte.
- Le client peut **modifier** ou **supprimer** pendant **30 jours** ; une modification repasse en attente (avis masqué en attendant).
- **Une réponse** de l'agence par avis, modifiable (pas de fil de discussion), affichée sous l'avis.
- Public : note moyenne et nombre d'avis (« **Pas encore d'avis** » sinon), avis publiés, plus récents d'abord, tri et filtre par étoiles. Seuls les avis **publiés** comptent.
- Personnel : avis à modérer (plus ancien d'abord), tous les avis filtrables, compteur ; voit toujours le **vrai client**.
- Destination désactivée : avis masqués, réapparaissent à la réactivation.

## Promotions (Récap 4)
- **Pourcentage** (1 à **50 %**) ou **montant fixe** (> 0, appliqué **une fois** par commande).
- Portée : tout le catalogue, pays ou destinations. Assiette : **séjour**, **activités** ou **total**.
- Prix jamais **sous 0 €**.
- Validité sur la **date de commande**, dernier jour inclus **jusqu'à minuit**, date de fin **≥** date de début ; période de départ optionnelle.
- **Automatique** ou **sur code** (4 à 20 lettres et chiffres, unique, saisie en minuscules acceptée) ; **un code par commande**.
- **Pas de cumul** : la plus grande remise en euros ; à égalité, la **plus récente**.
- Limites optionnelles (total, par client), comptées à la création, **rendues si annulation**.
- **Figée** dans la commande (remise, nom, montant économisé).
- États : À venir, En cours, Terminée, Désactivée ; suppression seulement si **jamais utilisée** ; une promo utilisée ne change que de nom, description et date de fin ; historique (date et auteur de chaque création, modification, désactivation) et administrateur créateur.
- **Administrateur** uniquement ; agents en consultation.
- Public : bandeau sur la fiche destination, étiquette « Promo » (promotions **automatiques** en cours), champ « Code promo » (« Code appliqué : -100 € » ou message simple) ; **récapitulatif** prix avant remise, remise, prix après remise ; les codes ne sont **jamais publics**.
- Page de statistiques par promotion (commandes, remises, clients ; annulées à part).

## E-mails (Récap 5, complété par le Récap 7)
- **Compte** : bienvenue + confirmation d'adresse (**48 h**, redemandable) ; mot de passe oublié (**1 h**) ; mot de passe modifié ; adresse modifiée (alerte à l'ancienne, confirmation demandée pour la nouvelle) ; compte supprimé (dernier message, puis plus aucun envoi). Le mot de passe n'est **jamais** envoyé.
- **Commandes** : créée ; confirmée (avec le conseiller et le prix définitif) ; annulée (client / agence avec explication) ; **rappel J-7** (commande confirmée : passeport, visa, décalage horaire, monnaie, repris de la fiche pays) ; **invitation à un avis** le lendemain du retour, avec un lien direct, seulement s'il n'y a pas encore d'avis.
- **Paiement** : confirmation de paiement ; échec ; rappels d'acompte et de solde ; annulation pour non-paiement ; confirmation de remboursement. Le **reçu** est envoyé par Stripe.
- **Avis** : publié ; refusé (motif, et rappel qu'il peut être corrigé dans les **30 jours**) ; réponse de l'agence.
- **Promotions** : seulement avec **consentement** (case non cochée par défaut à l'inscription, modifiable dans le profil) et adresse confirmée ; **désinscription en un clic** (obligation légale) ; envoi **manuel** par l'administrateur, qui choisit une promotion existante et rédige un texte.
- **Personnel** : invitation agent (**7 jours**, pas de mot de passe provisoire) ; nouvelle commande vers **reservations@horizons-lointains.be** ; pas d'e-mail pour les avis à modérer.
- Forme : `Horizons Lointains <noreply@horizons-lointains.be>`, réponses vers **info@horizons-lointains.be**, logo, ton chaleureux et sobre, vouvoiement, signature avec les coordonnées de l'agence, français uniquement ; l'administrateur modifie le **texte** des modèles, pas les champs variables.
- Fiabilité : un échec ne bloque **jamais** l'action ; **3 tentatives** puis « échec » avec la raison ; liste des échecs et renvoi manuel par les agents ; « **adresse à vérifier** » après plusieurs échecs.
- **Journal** : date, destinataire, type, objet, état, tentatives, commande ou compte lié ; ni contenu ni liens de sécurité ; conservé **1 an** ; compte supprimé : adresses effacées, seules des statistiques anonymes restent.
- **Mode test** : tout redirigé vers une adresse unique, activé par défaut hors production.
- Le **motif interne** n'apparaît jamais dans un e-mail.

## Statistiques et tableau de bord (Récap 6, mis à jour par les Récaps 7 et 8)
- Les **clients** ne voient aucune statistique.
- **Agents** (temps réel, sans chiffre d'affaires) : commandes en attente, en attente depuis **plus de 48 h** (rouge), avis à modérer, départs des **7 prochains jours** ; chiffres cliquables.
- **Administrateur** (mise à jour **toutes les heures**, heure affichée) :
  - période par date de **commande** (défaut) ou de **départ** ; raccourcis + période personnalisée ; comparaison avec la période précédente (couleur selon l'indicateur, « nouveau » au lieu de +∞ %) ;
  - commandes par état, taux de confirmation et d'annulation ;
  - ⚠️ montants : **estimé** (libellé imposé « Montant estimé des commandes confirmées », après remise), **définitif confirmé**, **réellement encaissé**, **remboursements** (Récap 7 ; le Récap 6 n'avait que l'estimé) ; total des remises ; montant annulé à part ; potentiel en attente ;
  - top 5 destinations et pays (commandes confirmées, avec le montant estimé), top 5 activités ; bas du classement (destinations **actives** seulement) ;
  - courbe sur 12 mois, barres par pays, répartition par état ;
  - promotions en cours et la plus efficace ;
  - avis : moyenne, nombre, 3 meilleures / moins bonnes destinations (**au moins 5 avis**) ;
  - clients : comptes créés, inscrits actifs, ayant commandé, taux de conversion ; les comptes supprimés gardent leurs commandes dans les totaux mais ne comptent plus parmi les inscrits ;
  - e-mails en échec (7 jours) et adresses à vérifier ;
  - délai de traitement : moyenne, pire cas, **% traité en 48 h** (week-end compris) ;
  - places (plus tard) : taux de remplissage, séances presque complètes ou vides, total des suppléments.
- **Signaux** à seuils modifiables : annulations > **25 %**, plus de **5** commandes en attente > 48 h, traitement en 48 h < **80 %**.
- **Export** Excel/CSV par l'administrateur uniquement : commandes de la période (numéro, dates de commande et de départ, destination, pays, voyageurs, montant estimé, remise, état), **numéro de client** sans nom ni coordonnées ; chaque export tracé (qui, quand, quelle période).
- Lisible sur téléphone.

## Tests unitaires du backend (Récap 9)
- Logique pure, **sans** base, réseau, vrai Stripe ni vrais e-mails (simulés) ; **horloge simulée** pour tous les délais.
- Priorité à l'**argent** : prix, promotions, échéancier (29 / 30 / 31 jours), remboursements, puis états, droits, places, Stripe, e-mails, comptes, avis, statistiques.
- Chaque règle de gestion couverte par **au moins un test**, avec un **tableau de correspondance** règle ➜ tests.
- Noms des tests **en français** ; test de **non-régression** pour chaque bogue.
- Couverture **80 %**, **100 %** sur prix, promotions, remboursements, échéancier, états, droits.
- Lancés **automatiquement** à chaque modification ; un échec bloque la mise en ligne ; **2 minutes** max ; rapport par domaine.
- Données **fictives** uniquement (« Marie Test », « Jean Exemple », `@exemple.test`).

## Contraintes générales
- Interface **lisible** (public plutôt âgé), ordinateur et téléphone, **français**, **RGPD**.
- Environ **1 000 clients** ; quelques centaines d'e-mails par jour (**1 000** lors d'un envoi promotionnel) ; ~**30 séances** ouvertes, plans de 20 à 300 places.

## Points encore à confirmer
- Remboursement aux jours pile : 30 j ➜ 100 %, 15 j ➜ 50 %, 14 j ➜ 0 % (avec le comptable).
- Délai de 48 h en **heures ouvrables** plutôt que réelles.
- **Statistiques par agent** (administrateur seulement, agents informés).
- **Compagnon** d'une personne à mobilité réduite assis à côté.
- Annulation par le client **après confirmation, avant paiement** : le Récap 7 dit qu'il peut annuler sans frais, les Récaps 2 et 9 qu'il ne peut pas annuler lui-même une commande confirmée. Retenu ici : sans frais, mais en appelant l'agence.
- « **Motif obligatoire** pour une annulation » (Récap 9, tests) : vise-t-il aussi le client, dont le motif est facultatif (Récap 2) ? Retenu ici : obligatoire pour le personnel seulement.
- Questions ouvertes des Récaps 3 et 4 : voir ces récaps (les réponses validées sont dans le README).

## Souhaitable
- Commandes dont le prix définitif dépasse l'estimation de **plus de 15 %** (tableau de bord).
- **Carte du monde** des pays les plus vendus.
- Bouton « **Placer ensemble** » ; icônes **fenêtre / couloir / place avec espace**.
- Page d'accueil : les **5 derniers avis à 5 étoiles** ; **avis négatifs en priorité** pour les conseillers.
- Page « **Nos offres du moment** ».
- Notes sur les **activités réalisées** pendant le voyage, dans l'avis (Récap 3).

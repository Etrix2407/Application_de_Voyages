# Récap 7 – Paiement des commandes via Stripe

## Principe
- Le client paie **directement dans l'application**, via **Stripe**.
- L'application ne voit et ne stocke **jamais** les données de carte : le paiement se fait sur la **page sécurisée de Stripe** (Checkout).
- Hors périmètre : **facturation** (faite à part par le comptable), **TVA**, **frais Stripe**, **versements** vers la banque, modification du prix **après paiement**.

## Quand payer
- **Jamais à la création** de la commande : le paiement vient **après la confirmation** par un agent.
- À la confirmation, l'agent saisit le **prix définitif** :
  - par défaut = prix estimé (**après remise**, la promotion reste figée, pas de recalcul) ;
  - modifiable, avec une **justification obligatoire** (ex. « supplément haute saison »).
- Le client voit l'**estimation initiale**, le **prix définitif** et la **justification**. Il peut **annuler sans frais avant de payer**.
- Le prix définitif n'est **plus modifiable après le premier paiement**.

## Comment payer
- Après la confirmation : e-mail + bouton « **Payer ma commande** » dans l'espace client.
- Page Stripe, puis retour dans l'application : « Merci, votre paiement est bien enregistré » (ou « Paiement non effectué » s'il abandonne).
- Moyens : **carte bancaire** (Visa, Mastercard) et **Bancontact**. Pas de PayPal ni de cryptomonnaie.
- **Euros** uniquement.

## Échéancier
- Départ dans **plus de 30 jours** : le client choisit « **Payer l'acompte (30 %)** » ou « **Payer la totalité** ».
  - **Solde** au plus tard **30 jours avant le départ**.
- Départ dans **moins de 30 jours** : **totalité** en une fois, pas d'acompte.

### Acompte (ou totalité) après confirmation
- Délai de **7 jours**.
- Rappels à **J+3** et **J+6**.
- Passé 7 jours : **annulation automatique**, motif « paiement non reçu ».

### Solde
- Rappels **45**, **35** et **31 jours** avant le départ.
- Non payé à **30 jours** du départ : le **conseiller est averti** et appelle le client. **Pas d'annulation automatique**.

## Sécurité du paiement
- Session de paiement valable **30 minutes**, ensuite il faut en créer une nouvelle.
- **Jamais de double paiement** : une seule demande de paiement **active** par commande et par échéance (double clic, deux onglets…).
- Paiement refusé : Stripe propose de réessayer ; le client peut **recommencer** depuis le bouton. Pas de limite de tentatives.
- Le **retour du navigateur ne fait pas foi** : seul le **webhook** Stripe (serveur à serveur) enregistre un paiement.
  - Stripe renvoie le webhook en cas d'échec ; un **administrateur** peut aussi **vérifier** l'état d'un paiement auprès de Stripe.
- Stripe indisponible : message « Le paiement est momentanément indisponible, réessayez dans quelques minutes ». La commande reste « À payer ».
- Compte Stripe de l'**agence**. Clés **jamais dans le code** ni dans un fichier lisible par tous.
- **Mode test** (fausses cartes) et **mode réel**, avec des clés séparées.

## États
- L'**état de la commande** (En attente, Confirmée, Annulée) ne change pas.
- Nouvel **état du paiement**, seulement pour une commande **confirmée** :
  - À payer ;
  - Acompte payé ;
  - Payé en totalité ;
  - Remboursé partiellement ;
  - Remboursé totalement.
- Un paiement refusé n'est **pas un état** : il va dans le **journal des tentatives** (chaque essai et son résultat). L'état reste « À payer ».

## Annulation et remboursement
- Annulation par **l'agence** : remboursement à **100 %**, quel que soit le motif.
- Annulation par le **client** :
  - plus de **30 jours** avant le départ : **100 %** ;
  - entre **30 et 15 jours** : **50 %** ;
  - moins de **15 jours** : **rien**.
- Le pourcentage s'applique à ce qui a été **réellement payé** (ex. 900 € d'acompte, annulation à 20 jours ➜ 450 €).
- **Pas automatique** : l'application **calcule** le montant, l'agent **propose**, l'**administrateur valide**.
  - L'administrateur peut **modifier** le montant (geste commercial) avec une **justification**.
- Le remboursement est **déclenché dans Stripe par l'application**.
- Remboursements **partiels successifs** possibles, mais **jamais plus que le total encaissé**.
- Message au client : remboursement « sous **5 à 10 jours ouvrables** ».

## E-mails ajoutés (en plus du Récap 5)
- **Confirmation de paiement** (« Nous avons bien reçu votre paiement de 900 euros »).
- **Échec de paiement** (signalé par Stripe).
- **Rappels** de paiement (acompte et solde).
- **Annulation pour non-paiement**.
- **Confirmation de remboursement** : montant et délai.
- Le **reçu** est envoyé par **Stripe** lui-même.

## Ce que chacun voit
- **Personnel** : montant définitif, montant payé, reste à payer, date d'échéance du solde, liste des paiements (date, résultat), remboursements, et un **lien vers le paiement dans Stripe** (pour le comptable).
- **Client** : prix définitif, montant payé, reste à payer, prochaine échéance. **Pas** de lien Stripe.
- Saisie du prix définitif : **agents**, à la confirmation.

## Statistiques (mise à jour du Récap 6)
- Distinguer **montant estimé**, **montant définitif confirmé** et **montant réellement encaissé**.
- Afficher les **remboursements**.

## Souhaitable
- Dans le tableau de bord : commandes dont le prix définitif dépasse l'estimation de **plus de 15 %** (contrôle des conseillers). Pas de limite imposée par le logiciel.

# Récap 5 – Envoi d'e-mails aux clients

## E-mails aux clients

### Compte
- **Création du compte** : e-mail de bienvenue avec un lien de **confirmation de l'adresse**, valable **48 h**. Si le lien est périmé, le client peut en redemander un lui-même.
  - Adresse non confirmée : le client peut se connecter et parcourir le catalogue, mais **ne peut pas commander**.
- **Mot de passe oublié** : lien de réinitialisation valable **1 h**. Le mot de passe n'est **jamais** envoyé par e-mail.
- **Mot de passe modifié** : e-mail de sécurité « Si ce n'est pas vous, contactez-nous ».
- **Adresse e-mail modifiée** : alerte envoyée à l'**ancienne** adresse, et confirmation demandée pour la nouvelle.
- **Compte supprimé** : dernier message « compte supprimé, données effacées », puis plus aucun envoi.

### Commandes
- **Commande créée** : accusé de réception (« un conseiller vous rappellera sous 48 h ») avec le récapitulatif : destination, dates, voyageurs, activités, prix estimé, promotion, et la mention « **estimation, non contractuelle** ».
- **Commande confirmée** : même récapitulatif, plus le **nom du conseiller**.
- **Commande annulée** :
  - par le client : accusé de réception ;
  - par l'agence : message avec le motif et un mot d'excuse.
  - ➜ Évolution des commandes : **2 champs**, un *motif interne* (visible du personnel seulement) et une *explication pour le client*. Si l'explication est vide, on envoie un message neutre.
- **Rappel J-7 avant le départ**, uniquement pour une **commande confirmée** : passeport, visa, décalage horaire et monnaie, repris de la fiche pays.
- **Lendemain du retour** : invitation à laisser un avis, avec un lien direct, seulement si le client n'a pas encore laissé d'avis.

### Avis
- Avis **publié** : « Merci, votre avis est en ligne ».
- Avis **refusé** : motif, et rappel qu'il peut le corriger dans les **30 jours**.
- **Réponse de l'agence** à un avis : notification au client.

### Promotions
- Envoyées seulement aux clients qui ont donné leur **consentement**. C'est une case **non cochée par défaut** à l'inscription, modifiable dans le profil.
- Lien de **désinscription en un clic** dans chaque message (obligation légale).
- Envoi **manuel** par l'administrateur, qui choisit une promotion existante et rédige un texte.
- Hors périmètre : pas de programmation, pas de ciblage, pas de statistiques d'ouverture.

## E-mails au personnel
- **Création d'un compte agent** : invitation avec un lien pour choisir son mot de passe, valable **7 jours**. Pas de mot de passe provisoire.
- **Nouvelle commande** : alerte envoyée à l'adresse commune **reservations@horizons-lointains.be**, pas à chaque agent.
- **Avis à modérer** : pas d'e-mail, le compteur du tableau de bord suffit.

## Forme
- Expéditeur : `Horizons Lointains <noreply@horizons-lointains.be>`. Réponses vers **info@horizons-lointains.be**.
- Logo, ton chaleureux avec **vouvoiement**, signature de l'agence avec les coordonnées, sobre.
- **Français uniquement** (pas de langue préférée pour l'instant).
- **Modèles de messages** : l'administrateur peut modifier le **texte**, mais pas la mise en page ni les **champs variables** (prénom, n° de commande, destination, dates, récapitulatif).

## Fiabilité et journal
- Un échec d'envoi ne doit **jamais bloquer** l'action : la commande est créée quand même.
- **3 tentatives** espacées de quelques minutes, puis état « **échec** », avec la raison.
- Les agents voient la **liste des échecs** et peuvent **renvoyer manuellement**.
- **Journal** des envois : date, destinataire, type, objet, état (en attente / envoyé / échec), nombre de tentatives, commande ou compte lié.
  - On ne conserve **pas le contenu** des messages, ni les liens de sécurité.
  - Conservation : **1 an**.
  - Compte supprimé : journal supprimé, ou adresses effacées. On garde seulement des statistiques anonymes.
- Adresse **non confirmée** : pas de promotions, mais les messages de service partent.
- Adresse invalide après plusieurs échecs : le client est marqué « **adresse à vérifier** » dans la liste des agents.

## Volume et tests
- Quelques centaines de messages par jour, jusqu'à **1 000** lors d'un envoi promotionnel.
- **Mode test** : tous les messages sont redirigés vers une adresse unique. Il est **activé par défaut** en dehors de la production.

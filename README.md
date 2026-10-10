# Application_de_Voyages

Application web (Python 3, Django 5.2) pour une agence de voyage. Elle gère les comptes des clients et du personnel, et propose un catalogue de pays, destinations et activités. Le cahier des charges est résumé dans [Recap.md](Recap.md) (v1 : comptes et catalogue), [Recap_2.md](Recap_2.md) (v2 : demandes de voyage), [Recap_3.md](Recap_3.md) (v3 : avis clients), [Recap_4.md](Recap_4.md) (v4 : promotions) et [Recap_5.md](Recap_5.md) (v5 : envoi d'e-mails, en cours de développement). Les énoncés ne sont jamais modifiés : les décisions prises ensuite avec la cliente sont décrites dans ce README.

## Sommaire

- [Démarrage rapide](#démarrage-rapide)
- [Guide d'utilisation](#guide-dutilisation)
- [Fonctionnalités par rôle](#fonctionnalités-par-rôle)
- [Règles de gestion appliquées](#règles-de-gestion-appliquées)
- [Promotions (v4) : décisions validées](#promotions-v4--décisions-validées)
- [E-mails (v5) : socle d'envoi](#e-mails-v5--socle-denvoi)
- [Tests](#tests)
- [Mise en production](#mise-en-production)
- [Structure du code](#structure-du-code)

## Démarrage rapide

Prérequis : Python 3.10 ou plus récent.

```bash
pip install -r requirements.txt
copy .env.example .env               # puis remplissez .env (voir ci-dessous)
cd trip_app
python manage.py migrate
python manage.py createsuperuser   # compte administrateur (la gérante)
python manage.py runserver
```

Ouvrez ensuite http://127.0.0.1:8000/ et connectez-vous avec le compte administrateur.

### Le fichier `.env` (réglages et secrets)

Les réglages se trouvent dans le fichier **`.env`**, à la racine du dépôt, créé à partir du modèle [.env.example](.env.example) où chaque réglage est expliqué. Il contient des secrets : il **n'est jamais commité** (protégé par `.gitignore`) et ne doit pas être partagé. Le site refuse de démarrer sans `DJANGO_SECRET_KEY`, même en développement, et sans `DJANGO_PASSWORD_PEPPER` en production : renseignez-les (commande de génération indiquée dans le modèle). Le modèle est réglé pour la production (`DJANGO_DEBUG=0`) : sur votre ordinateur, passez `DJANGO_DEBUG=1`. Les variables d'environnement définies dans Windows ou sur le serveur restent prioritaires sur ce fichier.

Pour **recevoir vraiment les e-mails** (Outlook / Hotmail) : dans `.env`, renseignez `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` (mot de passe d'application si la validation en deux étapes est activée) et `DJANGO_DEFAULT_FROM_EMAIL` (même adresse), puis passez `DJANGO_EMAIL_BACKEND` sur `django.core.mail.backends.smtp.EmailBackend`. Vérifiez avec `python manage.py sendtestemail votre@adresse`. L'expéditeur prévu, `Horizons Lointains <noreply@horizons-lointains.be>` (utilisé si `DJANGO_DEFAULT_FROM_EMAIL` est vide), ne fonctionnera qu'avec le serveur d'envoi du domaine, qui n'existe pas encore : avec Outlook, l'expéditeur doit rester l'adresse Outlook. En développement (`DJANGO_DEBUG=1`), le **mode test** est actif : renseignez aussi `DJANGO_EMAIL_TEST_RECIPIENT` (votre adresse) pour recevoir tous les e-mails, sinon ils restent affichés dans le terminal (voir [E-mails en développement](#e-mails-en-développement)).

### Données de démonstration (facultatif)

Pour essayer l'application sans tout saisir :

```bash
python manage.py load_demo
```

La commande crée :

- 3 pays **fictifs** dont le nom commence par « Exemple — ». Leurs langue, monnaie et description sont inventées : ce ne sont **pas** de vraies informations de voyage. L'un des pays est désactivé, pour montrer ce que voient les clients.
- Un compte client `client.demo@example.com` et un compte agent `agent.demo@example.com`. Leurs mots de passe sont générés au hasard et **affichés dans le terminal** : notez-les.
- 2 promotions « Exemple — », en cours pendant 180 jours à partir du jour de la commande : une **automatique** (-10 % sur le total, pour « Exemple — Pays des Lacs ») et une **sur code** (`EXEMPLE10`, -10,00 € sur le total, tout le catalogue). Elles n'ont pas d'historique ni d'auteur (« Créée par — ») : la commande ne crée pas de compte administrateur.
- 4 demandes de voyage du client démo, créées comme depuis le site (prix figés, promotion, historique), une par état :
  - « En attente », avec la promotion automatique ;
  - « Confirmée » par l'agent démo, avec le code `EXEMPLE10` ;
  - « Annulée » par le client ;
  - « Confirmée », au voyage **terminé** (départ il y a environ un mois) : ses dates et son historique sont reculés de 60 jours, car le site n'accepte que des départs à venir.
- 1 avis à 5 étoiles du client démo sur ce voyage terminé, **publié**.

La commande refuse de s'exécuter en production (`DJANGO_DEBUG=0`). Elle peut être relancée sans créer de doublons.

### E-mails en développement

En développement, aucun e-mail n'est réellement envoyé : il s'affiche dans le terminal où tourne `runserver`. C'est le cas des liens « mot de passe oublié » et des liens d'activation des agents. Copiez le lien affiché dans le navigateur.

C'est le **mode test**, actif par défaut dès que `DJANGO_DEBUG=1` (jamais en production) :

- `DJANGO_EMAIL_TEST_RECIPIENT` vide : les e-mails s'affichent dans le terminal, même si un serveur SMTP est réglé ;
- `DJANGO_EMAIL_TEST_RECIPIENT=votre@adresse` (avec le serveur SMTP réglé) : **tous** les e-mails partent à cette adresse, et l'objet commence par l'adresse d'origine (« [Test : marie@example.com] Confirmez votre inscription ») ;
- `DJANGO_EMAIL_TEST_MODE=0` : mode test désactivé, les e-mails partent aux vrais destinataires.

## Guide d'utilisation

### Premier démarrage (administrateur)

1. Créez le compte de la gérante avec `python manage.py createsuperuser` (e-mail, nom, prénom, mot de passe).
2. Connectez-vous, puis ouvrez le menu **Personnel** et cliquez sur **Créer un agent**.
3. L'agent reçoit un e-mail avec un lien valable 1 heure pour choisir son mot de passe. S'il a expiré, utilisez **Envoyer un lien de mot de passe** dans la liste du personnel.
4. Depuis **Personnel**, l'administrateur peut aussi :
   - modifier un membre ;
   - le promouvoir administrateur ou le rétrograder ;
   - le désactiver (il est déconnecté immédiatement) ou le réactiver ;
   - le supprimer.

   Il ne peut jamais faire ces actions sur son propre compte.

### Gérer le catalogue (agent ou administrateur)

1. Menu **Gestion du catalogue**, puis **Ajouter un pays**.
2. Cliquez sur le nom du pays pour ouvrir sa fiche. Ajoutez-y des **destinations**, puis des **activités**. Une activité peut être liée à une destination du même pays, ou à aucune.
3. Pour **masquer** un élément aux clients, modifiez-le et décochez **Actif** :
   - un pays désactivé masque toutes ses destinations et activités ;
   - une destination désactivée masque ses activités.
4. Un pays qui contient des destinations ou des activités **ne peut pas être supprimé** : désactivez-le.

Formats à respecter :

| Champ | Format |
|---|---|
| Fuseau horaire principal | Tapez la ville de référence du pays (ex. « tokyo ») et choisissez-la dans les suggestions (« Asie — Tokyo » ; pour un pays à plusieurs fuseaux, celle de la destination principale). Le décalage avec la Belgique (été, hiver et aujourd'hui) est **calculé automatiquement**, changements d'heure compris |
| Période idéale | Mois de début et mois de fin ; peut chevaucher l'année (novembre → mars). Facultative |
| Durée d'une activité | En minutes : `90` pour 1 h 30 |
| Photo | Fichier JPEG, PNG ou WebP de 5 Mo maximum, envoyé depuis l'ordinateur. Facultative ; une nouvelle photo remplace l'ancienne. Les données cachées de la photo (position GPS, appareil, date de prise de vue) sont retirées avant publication |
| Prix | En euros. Le prix « à partir de » d'une destination est facultatif |

### Gérer les clients (agent ou administrateur)

1. Menu **Clients** : liste par pages de 25, avec recherche par nom, prénom ou e-mail (sans tenir compte des accents).
2. **Corriger** permet de modifier le prénom, le nom, le téléphone et la date de naissance. L'e-mail et le mot de passe restent gérés par le client.
3. **Envoyer un lien de mot de passe** : le client reçoit un lien valable 1 heure pour choisir un nouveau mot de passe. L'agent ne voit jamais le mot de passe.

### Traiter les demandes de voyage (agent ou administrateur)

1. Menu **Demandes de voyage** : toutes les demandes, les plus récentes d'abord (tri inversable), par pages de 25.
2. Filtres : état, pays, destination, client (nom, prénom ou e-mail, sans tenir compte des accents) et période de départ.
3. Le détail d'une demande affiche le téléphone et l'e-mail du client (cliquables pour appeler ou écrire), les voyageurs, les activités aux prix figés, les remarques et l'historique.
4. Après avoir rappelé le client : **Confirmer la demande** (impossible une fois la date de départ passée : la demande ne peut alors plus qu'être annulée). **Annuler la demande** est possible tant qu'elle est en attente ou confirmée, avec un **motif interne obligatoire** (visible par le personnel seulement) et une **explication pour le client** facultative (affichée dans l'historique de sa demande ; vide, aucun motif ne lui est affiché). Chaque action est notée dans l'historique avec la date et votre nom (le client, lui, voit « Agence »).

### Modérer les avis (agent ou administrateur)

1. **Avis à modérer (N)** (menu) : les avis en attente de validation, du plus ancien envoi au plus récent ; un avis de 1 ou 2 étoiles porte le badge **Avis négatif**.
2. « Lire et modérer » : l'avis, sa signature publique et toujours le **vrai client** et sa demande, même pour un avis « Voyageur anonyme ».
3. **Publier l'avis**, ou **Refuser l'avis** (l'action porte sur la version que vous avez lue : si le client l'a modifiée entre-temps, relisez-la) avec un motif de la liste (langage injurieux, hors sujet, coordonnées personnelles, autre) et une précision, obligatoire pour « Autre ». Un avis publié peut être **masqué** de la même façon. Le client voit le motif. Le texte d'un client n'est jamais modifié.
4. **Tous les avis** (lien depuis « Avis à modérer ») : tous les avis, du plus récent au plus ancien, 25 par page, filtrables par état, pays, destination, note, **avis négatifs seulement**, date de l'avis et date du séjour.
5. **Répondre à l'avis** (avis publié uniquement) : une seule réponse par avis, publique, signée de votre **prénom**. Seul son auteur peut la modifier (un administrateur si l'auteur a quitté l'agence : compte supprimé ou désactivé). Si le client modifie son avis, la réponse est supprimée.

### Gérer les promotions (administrateur ; agents en consultation)

1. Menu **Promotions** : toutes les promotions, les plus récentes d'abord, avec leur remise, leur portée, leur code et leur état (**À venir**, **En cours**, **Terminée** ou **Désactivée**). Les agents consultent la liste et les fiches pour renseigner les clients ; seul l'administrateur peut agir.
2. **Créer une promotion** :
   - un nom et une description courte facultative ;
   - une remise en **pourcentage** (de 1 à 50 %) ou en **montant fixe** (appliqué une fois par demande) ;
   - une portée : tout le catalogue, des pays ou des destinations (cases à cocher) ;
   - une assiette : séjour, activités ou total ;
   - des dates de validité, qui portent sur la date de la demande (dernier jour inclus) ;
   - une période de départ, facultative ;
   - un code, facultatif : sans code, la promotion est automatique. Il compte de 4 à 20 lettres sans accents ou chiffres, et une saisie en minuscules est acceptée ;
   - des limites d'utilisation, facultatives.
3. **Modifier** : la date de fin peut être avancée, mais pas placée dans le passé. Chaque modification est notée dans l'**historique** de la fiche, avec la date, l'auteur et les champs modifiés.
4. **Désactiver** : la promotion n'est plus proposée mais reste dans l'historique. **Supprimer** n'est possible que pour une promotion jamais utilisée.
5. Un pays ou une destination visé par une promotion ne peut pas être supprimé : désactivez-le.
6. **Statistiques** (lien depuis la fiche, agents et administrateur) : nombre de demandes qui ont utilisé la promotion, total des remises accordées (pour une demande confirmée, la remise recalculée à la confirmation), nombre de clients différents, et liste des demandes avec un lien vers chacune. Les demandes annulées ne comptent dans aucun chiffre et sont listées à part. Les demandes de clients ayant supprimé leur compte sont comptées dans les demandes (« dont 2 demandes de clients ayant supprimé leur compte ») mais pas dans les clients différents : on ne peut plus savoir de qui il s'agit.

### Utiliser l'application (client)

1. **Créer un compte** : remplissez le formulaire, **choisissez votre mot de passe** (saisi deux fois) et acceptez la politique de confidentialité. Le compte est utilisable tout de suite (connexion, catalogue, favoris), mais **aucune demande de voyage ne peut être envoyée tant que l'adresse n'est pas confirmée**. Un e-mail contient un lien de confirmation, valable 48 heures ; la page ouverte par le lien affiche les informations du compte et demande un clic sur « Confirmer mon adresse ». Lien périmé ou rien reçu ? « Renvoyer l'e-mail de confirmation » depuis la page de connexion, ou, une fois connecté, depuis **Mon profil** ou le message affiché quand une demande de voyage est refusée (3 envois par heure au plus pour une même adresse). Une nouvelle inscription avec l'adresse d'un compte non confirmé remplace ce compte (favoris compris). Un compte jamais confirmé est effacé au bout de 30 jours. Le téléphone est facultatif ; s'il est rempli, il doit être un numéro belge (0470 12 34 56) ou international avec l'indicatif du pays (+33 6 12 34 56 78).
2. **Nos pays** : le catalogue (pays, destinations, activités) et la recherche sont visibles par tous, même sans compte. Il faut être connecté pour enregistrer des favoris et faire une demande de voyage. Le menu **Destinations** liste toutes les destinations avec leur **note moyenne** (« ★ 4,6 sur 5 (23 avis) » ou « Pas encore d'avis »), également affichée sur la fiche pays, dans la recherche et les favoris. La page d'**accueil** présente les 5 derniers avis publiés à 5 étoiles. La fiche d'une destination montre ses **avis vérifiés** (badge « ✓ Voyage vérifié — séjour de mars 2026 »), triables (plus récents ou meilleures notes) et filtrables par nombre d'étoiles, 10 par page.
   **Promotions** : le menu **Nos offres du moment**, visible par tous, liste les promotions automatiques en cours (nom, description, remise et partie du prix concernée, pays ou destinations visés, date de fin, période de départ éventuelle). La fiche d'une destination visée affiche un bandeau (« Semaine du Japon : -15 % sur le séjour jusqu'au 31 mars 2027, pour les départs du … au … »), et sa carte porte l'étiquette **Promo** dans la liste des destinations, la fiche pays et la recherche. Les promotions sur code, désactivées, à venir, terminées ou dont le maximum de demandes est atteint n'y apparaissent jamais ; un pays ou une destination désactivé n'est pas cité.
3. **Rechercher** : recherche par mot-clé (sans tenir compte des accents) et filtres. Un filtre ne s'applique qu'au type de résultat qu'il concerne :

   | Filtre | S'applique à |
   |---|---|
   | Continent | Pays, destinations et activités |
   | Budget maximum | Destinations (prix « à partir de » ; une destination sans prix reste affichée) et activités (prix par personne) |
   | Mois de voyage | Destinations dont la période idéale inclut ce mois |
   | Catégorie, difficulté, âge du voyageur | Activités |

4. **Demande de voyage** : sur la page d'une destination, « Faire une demande de voyage ». Choisissez les dates (départ au moins 7 jours plus tard et dans les deux ans, séjour de 90 jours au maximum), le nombre d'adultes et d'enfants (10 voyageurs au plus), les activités du pays et vos remarques (2 000 caractères au plus). 10 demandes au maximum par 24 heures. Un champ **Code promo** est facultatif : les promotions sans code s'appliquent seules, et la plus avantageuse l'emporte (pas de cumul). Une page de vérification affiche le **prix estimé** (estimation, non contractuel ; enfants à 50 %) avant l'envoi, avec le prix avant remise, la remise et le prix après remise s'il y a une promotion. Un code refusé est expliqué simplement (« Ce code a expiré », « Vous avez déjà utilisé ce code »…). Un conseiller vous rappelle sous 48 heures.
   **Mes demandes** (menu) : liste de vos demandes (destination, dates, état, prix estimé), détail avec l'historique (les actions du personnel y apparaissent sous le nom « Agence »). Tant qu'une demande est « En attente », vous pouvez l'annuler (motif facultatif) ; une demande confirmée s'annule en appelant l'agence.
5. **Favoris** : le bouton « Ajouter à mes favoris » se trouve sur la page d'une destination ou d'une activité. Retrouvez-les dans **Mes favoris**. Un favori devenu indisponible y reste signalé et peut être retiré.
6. **Mes avis** (menu) : après un voyage **confirmé par l'agence**, une fois rentré, « Donner mon avis » (sur la demande ou dans « Mes avis ») : note de 1 à 5 étoiles, titre, commentaire (obligatoire pour 1 ou 2 étoiles), signature « Prénom N. » ou « Voyageur anonyme ». L'avis est publié après validation par l'agence ; son état et, le cas échéant, le motif du refus sont visibles dans « Mes avis ». Il reste **modifiable 30 jours** après sa création ; une modification le renvoie en validation (masqué en attendant). Il peut être **supprimé à tout moment**, mais ce voyage ne pourra alors plus recevoir d'avis. La signature (« Julie D. ») est fixée à l'envoi de l'avis : changer son nom ensuite ne modifie pas un avis publié.
7. **Mon profil** : modifier ses informations, changer son mot de passe, **changer son adresse e-mail** (mot de passe demandé, puis lien de confirmation envoyé à la nouvelle adresse ; l'ancienne est prévenue ; si l'adresse du compte n'était pas encore confirmée, confirmer la nouvelle adresse confirme aussi le compte) ou **supprimer son compte**. La suppression est définitive et efface aussi les favoris. **Télécharger mes données** fournit un fichier JSON avec ses informations de compte (sans le mot de passe), ses demandes de voyage, ses avis (avec la réponse de l'agence), ses favoris et la liste des e-mails reçus (sans leur contenu).

### Mot de passe oublié

Sur la page de connexion, **Mot de passe oublié ?** envoie un lien valable 1 heure (3 demandes par heure au plus pour une même adresse, contre les envois en masse).

Limites par adresse IP, contre les robots : 20 échecs de connexion par 15 minutes, 5 inscriptions, 10 demandes de lien et 30 codes promo faux par heure ; et, dans l'heure qui suit une inscription depuis cette IP, 3 échecs de connexion suffisent à la bloquer 15 minutes. Elles sont volontairement larges, car un bureau ou un wifi partage souvent une même IP. Après 5 tentatives de connexion échouées, la connexion est bloquée 15 minutes pour cette adresse e-mail.

## Fonctionnalités par rôle

| Rôle | Fonctionnalités |
|---|---|
| Visiteur | Catalogue complet (pays, destinations, activités) ; page « Destinations » avec les notes ; lecture des avis vérifiés ; recherche et filtres ; inscription ; connexion |
| Client | Détail des pays, destinations et activités ; recherche et filtres ; favoris ; demandes de voyage (faire une demande une fois l'adresse e-mail confirmée, suivre et annuler ses demandes en attente) ; avis sur ses voyages terminés (donner, modifier 30 jours, supprimer) ; profil (modifier, changer le mot de passe ou l'adresse e-mail, télécharger ses données, supprimer le compte) |
| Agent | Consultation et recherche ; gestion du catalogue ; liste des clients, correction de leurs informations (sauf e-mail et mot de passe), envoi d'un lien de mot de passe ; traitement des demandes de voyage (filtrer, confirmer, annuler avec motif) ; modération des avis (publier, refuser ou masquer avec motif), réponse de l'agence, liste filtrée de tous les avis ; consultation des promotions ; profil (consultation, changement du mot de passe, téléchargement de ses informations de compte et de la liste des e-mails reçus au format JSON) |
| Administrateur | Droits de l'agent + gestion du personnel + gestion des promotions (créer, modifier, désactiver, supprimer si jamais utilisée) |

## Règles de gestion appliquées

- Un compte = une adresse e-mail unique, sans tenir compte des majuscules.
- Mots de passe hachés (jamais stockés en clair) : au moins 12 caractères, avec au moins une lettre et un chiffre. Les mots de passe trop courants ou trop proches du nom ou de l'e-mail sont refusés.
- Hachage PBKDF2-SHA256 avec un **sel** aléatoire propre à chaque mot de passe (stocké dans la base) et un **poivre** (`DJANGO_PASSWORD_PEPPER`, gardé dans le `.env`, hors de la base) : une base volée seule ne suffit pas. **Sauvegardez le poivre à part : le perdre ou le changer rend tous les mots de passe inutilisables** (chacun devrait passer par « Mot de passe oublié »). Les anciens mots de passe sans poivre sont convertis à la connexion suivante.
- Un nom de pays est unique, sans tenir compte des majuscules ni des accents (« Perou » = « Pérou »).
- **Avis vérifiés (v3)** : un avis ne peut être laissé que pour une demande de voyage **confirmée par l'agence** dont la **date de retour est passée** : seuls les clients réellement partis donnent leur avis. Un seul avis par demande (garanti par la base). Si l'agence annule ensuite ce voyage, l'avis est retiré automatiquement (« Refusé », motif « Voyage annulé »).
- Avis : seule la **destination** est notée ; les activités réalisées ne sont pas notées (option « souhaitable » du Recap 3 écartée par la cliente). Limites : titre 100 caractères, commentaire 1 000, réponse de l'agence 1 000, précision d'un refus 500.
- Avis et **compte supprimé** : les avis restent publiés, signés « Voyageur anonyme », sans lien avec la personne (signature « Julie D. » effacée en base ; le personnel voit « Client supprimé »), et comptent toujours dans les notes. Avis et **destination ou pays désactivé** : les avis restent en base mais ne sont plus visibles ni comptés ; ils réapparaissent à la réactivation.
- **Promotion d'une demande** : son nom et la remise sont figés dans la demande ; modifier ou désactiver la promotion ne change rien aux demandes existantes. À la confirmation, la remise est ré-appliquée au prix recalculé. Une promotion déjà utilisée ne change plus que de nom, de description et de date de fin, et ne peut plus être supprimée. Une demande annulée rend l'utilisation (limites par client et au total).
- Une demande de voyage garde les **noms** (pays, destination, activités) et l'**estimation** du jour où elle a été envoyée : un renommage ou un changement de tarif dans le catalogue ne les modifie pas. À la **confirmation**, le prix est **recalculé aux tarifs du jour** (le prix peut varier entre la demande et la confirmation) ; l'estimation de départ reste affichée, et un changement de prix est noté dans l'historique.
- Un client ne voit jamais les données d'un autre client ni celles du personnel. Les agents ne voient pas les favoris des clients.
- RGPD : consentement enregistré à l'inscription, page [politique de confidentialité](trip_app/templates/privacy.html), suppression réelle du compte par le client, téléchargement de ses données au format JSON (droit à la portabilité) : chaque application fournit les siennes (`services/data_export.py`), assemblées par la vue `accounts/views/data_export.py`.
- RGPD, demandes de voyage : à la suppression d'un compte client, ses demandes sont conservées pour les statistiques, sans lien vers le compte (remarques et motifs effacés, motifs internes compris) ; seule une empreinte non lisible de l'adresse e-mail (HMAC) est gardée, pour appliquer les limites des promotions par client. Ses demandes encore « En attente » sont **annulées automatiquement** (motif interne « Compte client supprimé ») : le personnel n'a plus personne à rappeler ; les demandes confirmées restent confirmées, marquées « Client supprimé ». Automatique quel que soit le chemin de suppression (`orders/signals.py`).
- Inscription avec une adresse déjà confirmée : aucun compte n'est créé, la page affichée est identique et la propriétaire de l'adresse est prévenue par e-mail. Limite atténuée : le compte étant utilisable avant confirmation, essayer de se connecter avec le mot de passe choisi permet de savoir si l'adresse avait déjà un compte confirmé ; pour freiner ce test en série, une adresse IP qui s'est inscrite dans l'heure est bloquée 15 minutes après 3 échecs de connexion.
- Inscription avec l'adresse de quelqu'un d'autre (« pré-détournement ») : un tiers peut créer un compte non confirmé avec une adresse qui n'est pas la sienne et un mot de passe qu'il connaît. La page de confirmation affiche donc les informations du compte (nom, téléphone, date de naissance) et demande un clic sur un bouton : la vraie propriétaire de l'adresse voit que ce compte n'est pas le sien et, au lieu de le confirmer, recommence l'inscription, ce qui le remplace par le sien. Ouvrir le lien ne confirme rien.
- Clients non confirmés : la demande de voyage est refusée à la fois par la vue et par le service (`orders/services/placing.py`). Le personnel n'est pas concerné.

## Promotions (v4) : décisions validées

Version terminée. Le [Recap_4.md](Recap_4.md) décrit les promotions ; voici les réponses de la cliente à ses questions ouvertes et aux cas qu'il ne couvrait pas. La « commande » du Recap est la **demande de voyage** de l'application.

- **Calcul** :
  - la remise s'applique **après** le demi-tarif enfant ;
  - un montant fixe est **plafonné** à son assiette (-100,00 € « sur les activités » pour 60 € d'activités = 60 € de remise) ;
  - une promotion qui donnerait 0 € (ex. « sur les activités » sans activité, « sur le séjour » pour une destination sur devis) est **non applicable** et n'est pas comptée comme utilisée.
- **Confirmation** : quand l'agent recalcule le prix aux tarifs du jour, la promotion figée dans la demande est **ré-appliquée** (un pourcentage reste un pourcentage, un montant fixe reste le même montant).
- **Meilleure promotion** :
  - en cas d'égalité, la promotion **créée le plus récemment** l'emporte ;
  - si une promotion automatique bat le code saisi, le client lit « Une offre plus avantageuse s'applique déjà : -150,00 € » et son code **n'est pas consommé**.
- **Messages du code promo**, en plus des cinq du Recap :
  - « Ce code ne s'applique pas à ces dates de départ » (départ hors de la période autorisée) ;
  - un code dont la promotion n'a pas encore commencé donne « Code invalide », pour ne pas révéler les offres à venir.
- **Sécurité** : 10 codes faux par heure au plus pour un client et 30 par adresse IP (tous comptes confondus), contre les essais au hasard.
- **Envoi de la demande** : si la remise change entre la page de vérification et l'envoi (promotion expirée, dernière utilisation prise), la demande n'est pas envoyée et le client revoit le récapitulatif avec le nouveau prix. Pour un code promo, il revoit le formulaire avec le message sous le champ « Code promo ». Les limites sont revérifiées au moment de l'enregistrement : si deux clients envoient leur demande au même instant pour la dernière utilisation, un seul l'obtient.
- **Limite par client** : le client est reconnu à une empreinte de son adresse e-mail (sans majuscules ni partie « +… » : moi+1@exemple.com = moi@exemple.com), enregistrée dans la demande et conservée après la suppression du compte : une réinscription avec la même adresse ne remet pas le compteur à zéro. Si le client change d'adresse, l'empreinte de toutes ses demandes est recalculée : la limite le suit. Changer `DJANGO_SECRET_KEY` remet en revanche tous ces compteurs à zéro.
- **Promotion déjà utilisée** : seuls le **nom**, la **description** et la **date de fin** restent modifiables ; pour changer le reste, on crée une nouvelle promotion.
- **Dates** :
  - la date de fin peut être avancée, mais **pas avant aujourd'hui** ; pour arrêter une promotion tout de suite, on la désactive ;
  - la période de départ a ses deux dates remplies ensemble, la fin étant postérieure ou égale au début.
- **Portée** :
  - pas de ciblage par catégorie d'activités ;
  - un pays ou une destination visé par une promotion **ne peut pas être supprimé** : on le désactive.
- **Auteur** : le nom de l'administrateur reste affiché dans la promotion et son historique, même si son compte est supprimé.
- **Statistiques** : les demandes annulées sont **exclues de tous les chiffres** et listées à part.
- **Page « Nos offres du moment »** : retenue. Elle liste les promotions automatiques en cours, jamais les codes.

> **Avant la mise en ligne :** dans la politique de confidentialité, remplacez l'adresse e-mail **fictive** `vie-privee@horizons-lointains.example` par la vraie adresse de contact et ajoutez l'adresse postale de l'agence (rappel en commentaire dans `trip_app/templates/privacy.html`).

## E-mails (v5) : socle d'envoi

Tous les e-mails du site passent par un seul service, `accounts/services/emails.py` (dans `accounts`, la première application : toutes les autres peuvent l'utiliser) :

```python
send_email(to, kind, template_name, context, *, user=None, order_number=None) -> bool
```

- `kind` : type de l'e-mail (`EmailKind`, dans `accounts/models.py`), clé stable qui fixe l'objet ; elle servira à rendre les textes modifiables par l'administrateur. Chaque nouvel e-mail ajoute son type et son objet (`SUBJECTS`).
- `template_name` : gabarit du **texte**, qui commence par `{% autoescape off %}`. La version **HTML** est construite à partir de ce texte, dans la mise en page commune `templates/emails/base.html` (liens cliquables, gros caractères) : un seul texte à écrire par e-mail.
- `context` : variables du gabarit. Les liens sont absolus : `request.build_absolute_uri(...)` pendant une requête, `site_url(reverse(...))` dans une commande planifiée (réglage `DJANGO_SITE_URL`).
- `user`, `order_number` : compte et demande de voyage concernés, notés dans le journal.

Fonctionnement :

- L'e-mail part **après la validation de la transaction** en cours (immédiatement hors transaction). Un échec d'envoi ne bloque **jamais** l'action : il est noté dans le journal et dans les logs. La fonction renvoie `False` seulement si l'envoi immédiat a échoué (le personnel voit alors « Le lien n'a pas pu être envoyé »).
- Expéditeur `DJANGO_DEFAULT_FROM_EMAIL`, réponses vers `DJANGO_EMAIL_REPLY_TO` (défaut : info@horizons-lointains.be), délai SMTP `DJANGO_EMAIL_TIMEOUT` (10 secondes).
- Chaque e-mail (texte et HTML) se termine par la signature « L'équipe Horizons Lointains ». Logo et coordonnées de l'agence (ajoutées sous la signature) : réglages `EMAIL_LOGO_STATIC_PATH` et `EMAIL_SIGNATURE_LINES` de `config/settings.py`, **vides** tant qu'ils ne sont pas fournis (la mise en page ne les affiche pas). Le logo est un fichier de `static/`, affiché par son adresse complète (`DJANGO_SITE_URL` + chemin) : rien n'est joint au message, et si la messagerie bloque les images, le nom de l'agence s'affiche à la place.
- **Journal** (`EmailLog`) : une ligne par e-mail avec la date, le destinataire, le type, l'objet, l'état (en attente / envoyé / échec), le nombre de tentatives, la raison du dernier échec, le compte et la demande de voyage liés. Le **contenu** des messages et leurs **liens de sécurité** ne sont **jamais** conservés. Un envoi qui échoue reste « en attente » jusqu'à la 3e tentative, puis passe en « échec ». La demande est liée par son numéro, sans clé étrangère : `accounts` ne dépend pas de `orders`.
- **Télécharger mes données** : le fichier JSON contient aussi la liste des e-mails reçus (`emails` : date, type, objet, état), pour les clients comme pour le personnel.
- **Consentement aux e-mails promotionnels** (clients) : case facultative, **non cochée par défaut**, à l'inscription et dans « Modifier mes informations » (un agent ne peut pas la changer). Enregistré dans `accepts_promotional_emails` avec la date du dernier changement du choix (`promotional_emails_choice_date`, posée à l'accord comme au retrait : date de l'accord si le choix est accepté, du retrait sinon ; vide si le client n'a jamais accepté), à ne pas confondre avec `consent_date` (politique de confidentialité). Les comptes existants n'ont pas consenti. Les destinataires d'un envoi promotionnel sont donnés par `User.objects.promotion_recipients()` : clients actifs, consentants, à l'adresse confirmée. Le fichier « Télécharger mes données » contient ce choix et sa date.
- **Compte supprimé** : les lignes du journal restent (statistiques anonymes), sans adresse ni lien vers le compte (`accounts/signals.py`, quel que soit le chemin de suppression).

## Tests

```bash
cd trip_app
python manage.py test
```

Les tests utilisent un hachage de mot de passe rapide pour aller plus vite. L'application, elle, garde un hachage sécurisé (PBKDF2).

Un `TestCase` ne valide jamais sa transaction : les e-mails, envoyés après validation, n'y partent pas d'eux-mêmes. Une classe de tests qui vérifie des e-mails hérite de `SendEmailsImmediately` (`accounts/tests/email_delivery.py`), ou entoure l'action de `self.captureOnCommitCallbacks(execute=True)`.

## Mise en production

Réglez ces variables dans le `.env` du serveur, ou directement comme variables d'environnement chez l'hébergeur :

| Variable | Rôle | Défaut |
|---|---|---|
| `DJANGO_DEBUG` | `1` en développement, `0` en production | `0` (désactivé si absent) |
| `DJANGO_SECRET_KEY` | Clé secrète longue et aléatoire (obligatoire, même en développement) | aucun |
| `DJANGO_PASSWORD_PEPPER` | « Poivre » des mots de passe, long et aléatoire (obligatoire si `DJANGO_DEBUG=0`). **Ne jamais le perdre ni le changer** : tous les mots de passe deviendraient inutilisables | vide |
| `DJANGO_ALLOWED_HOSTS` | Noms de domaine autorisés, séparés par des virgules | vide |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` pour envoyer de vrais e-mails | console |
| `DJANGO_EMAIL_HOST` / `DJANGO_EMAIL_PORT` | Serveur SMTP | `localhost` / `587` |
| `DJANGO_EMAIL_HOST_USER` / `DJANGO_EMAIL_HOST_PASSWORD` | Identifiants SMTP | vides |
| `DJANGO_EMAIL_USE_TLS` | `1` pour chiffrer la connexion SMTP | `1` |
| `DJANGO_DEFAULT_FROM_EMAIL` | Expéditeur des e-mails (avec Outlook : l'adresse Outlook) | `Horizons Lointains <noreply@horizons-lointains.be>` |
| `DJANGO_EMAIL_REPLY_TO` | Adresse des réponses (en-tête Reply-To) ; vide = pas d'en-tête | `info@horizons-lointains.be` |
| `DJANGO_EMAIL_TIMEOUT` | Délai maximal d'attente du serveur SMTP, en secondes | `10` |
| `DJANGO_SITE_URL` | Adresse du site (ex. `https://horizons-lointains.be`), pour les liens et le logo des e-mails envoyés hors d'une requête. **Obligatoire en production** | `http://127.0.0.1:8000` en développement, vide en production |
| `DJANGO_EMAIL_TEST_MODE` | `0` pour désactiver le mode test en développement (toujours désactivé si `DJANGO_DEBUG=0`) | `1` |
| `DJANGO_EMAIL_TEST_RECIPIENT` | Mode test : adresse qui reçoit tous les e-mails ; vide = affichage dans le terminal | vide |
| `DJANGO_SECURE_SSL_REDIRECT` | `1` pour rediriger HTTP vers HTTPS | `1` |
| `DJANGO_HSTS_SECONDS` | Durée HSTS en secondes (ex. `31536000`), à activer une fois le HTTPS validé | `0` |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | `1` pour appliquer HSTS aux sous-domaines (seulement s'ils sont tous en HTTPS) | `0` |
| `DJANGO_NUM_PROXIES` | Nombre de serveurs intermédiaires (proxy) de confiance devant le site, pour retrouver l'IP réelle des visiteurs. Laisser `0` si le site est en accès direct : sinon une IP pourrait être falsifiée. Avec un proxy, celui-ci doit aussi transmettre `X-Forwarded-Proto` (origine HTTPS) en remplaçant toujours l'en-tête reçu | `0` |

Avec `DJANGO_DEBUG=0`, les cookies de session et CSRF ne sont envoyés qu'en HTTPS. Vérifiez la configuration avec :

```bash
python manage.py check --deploy
python manage.py collectstatic
```

### Activer HSTS

HSTS (en-tête `Strict-Transport-Security`) demande aux navigateurs de n'utiliser que le HTTPS pour ce site pendant la durée indiquée dans `DJANGO_HSTS_SECONDS`. Il est désactivé par défaut (`0`), car une erreur de réglage peut rendre le site inaccessible.

1. Activez-le seulement quand tout le site fonctionne en HTTPS avec un certificat valide.
2. Commencez par une petite valeur pour tester, par exemple `DJANGO_HSTS_SECONDS=3600` (une heure).
3. Si tout fonctionne, passez à `DJANGO_HSTS_SECONDS=31536000` (un an), la valeur retenue pour ce site.

**Attention** : une fois l'en-tête reçu, les navigateurs refusent le HTTP pour ce site pendant toute la durée choisie, même si vous remettez ensuite `0` ou si le certificat expire. N'activez `DJANGO_HSTS_INCLUDE_SUBDOMAINS` que si tous les sous-domaines sont eux aussi en HTTPS : la même règle s'applique alors à eux.

Points d'attention :

- Planifiez chaque jour `python manage.py purge_unconfirmed` (tâche planifiée Windows ou cron) : elle efface les comptes clients dont l'adresse n'a pas été confirmée dans les 30 jours (RGPD).
- **Ne committez jamais** la clé secrète ni les identifiants SMTP.
- Les limites anti-abus (5 échecs de connexion, 3 liens « mot de passe oublié » par heure, 5 essais quand le mot de passe est redemandé, etc.) sont stockées dans le dossier `trip_app/cache/` (créé automatiquement, jamais commité) : elles sont partagées par tous les processus du serveur et conservées au redémarrage. Ce dossier doit être accessible en écriture par le serveur. Les adresses IPv6 sont comptées par réseau /64.
- SQLite suffit pour le volume prévu (environ 1 000 clients).
- Les photos envoyées sont stockées dans `trip_app/media/` (hors git). En développement, Django les sert lui-même ; en production, configurez le serveur web pour servir ce dossier à l'adresse `/media/`, et sauvegardez-le avec la base. Ajoutez sur `/media/` l'en-tête `X-Content-Type-Options: nosniff` et interdisez toute exécution de script dans ce dossier.
- Recommandé : faire envoyer par le serveur web l'en-tête `Content-Security-Policy: default-src 'self'` (le site n'utilise ni script ni style externe).
- Durée de connexion : **8 heures pour le personnel** (poste partagé à l'agence), 2 semaines pour les clients.

## Structure du code

Le code (identifiants, fichiers, routes internes) est en anglais ; l'interface, les adresses visibles, les commentaires et la documentation sont en français.

```
trip_app/
├── config/                 # paramètres, routes et page d'accueil (views.py) du projet ; tests transversaux (droits d'accès, nombre de requêtes)
├── common/                 # outils partagés entre applications (normalisation du texte)
├── accounts/               # comptes : utilisateurs, rôles, RGPD ; journal des e-mails (v5)
│   ├── views/              # auth, profile, data_export, staff, clients (une responsabilité par module)
│   ├── services/           # inscription, changement d'e-mail, emails (envoi de tous les e-mails du site
│   │                       # et journal), password_links (liens de mot de passe), règles du personnel,
│   │                       # recherche de client, limites anti-abus, privacy (effacement RGPD du journal)
│   ├── models.py · forms.py · validators.py · decorators.py · urls.py
│   └── tests/
├── catalog/                # catalogue : pays, destinations, activités, favoris
│   ├── views/              # browse, search, favorites, manage
│   ├── services/           # recherche et filtres, favoris, nettoyage des photos
│   ├── models.py · forms.py · validators.py · urls.py
│   └── tests/
├── promotions/             # promotions (v4) : modèle, règles, historique
│   ├── views/              # manage (administrateur ; consultation par les agents), public (« Nos offres du moment »)
│   ├── services/           # discounts (calcul de la remise, meilleure offre), management, history,
│   │                       # public (offres affichées : bandeau, étiquette « Promo », page des offres)
│   ├── models.py · forms.py · urls.py
│   └── tests/
├── orders/                 # demandes de voyage (v2) : modèles, prix estimé, historique
│   ├── views/              # client (faire, suivre, annuler), manage (personnel)
│   ├── services/           # pricing, placing (création), promotions (choix de la promotion), status (changements d'état),
│   │                       # filtering (liste du personnel), privacy (anonymisation RGPD),
│   │                       # promotion_statistics (statistiques d'une promotion)
│   ├── models.py · forms.py · signals.py · urls.py
│   └── tests/
├── reviews/                # avis clients (v3) : modèle, avis vérifiés, lien avec les demandes
│   ├── views/              # client (donner, modifier, supprimer), manage (modération)
│   ├── services/           # eligibility, writing (client), moderation, responses, filtering (personnel),
│   │                       # ratings (notes publiques), order_events, privacy (effacement RGPD des signatures)
│   ├── management/commands/load_demo.py  # données de démonstration de toutes les versions
│   ├── models.py · forms.py · signals.py · urls.py · context_processors.py (compteur du menu)
│   └── tests/
├── templates/
│   ├── base.html · home.html · privacy.html · 403/404/500.html
│   ├── emails/             # base.html : mise en page HTML commune à tous les e-mails
│   ├── accounts/           # auth/ · profile/ · staff/ · clients/ · emails/ (textes des e-mails)
│   ├── catalog/            # pages publiques, fragments _*.html, manage/
│   ├── orders/             # demandes côté client, fragments _*.html, manage/
│   ├── promotions/         # offers.html (offres du moment), fragment _offer_terms.html, manage/ (gestion)
│   └── reviews/            # avis côté client, fragments publics _*.html, manage/ (modération)
└── static/css/             # feuille de style (texte lisible, adaptée au mobile)
```

Règle de rangement : les **vues** ne font que recevoir la requête et afficher la page ; la logique réutilisable va dans **services/** ; un outil utilisé par plusieurs applications va dans **common/**.

Dépendances entre applications : les **modèles et services** suivent l'ordre `accounts ← catalog ← promotions ← orders ← reviews` (une application ne dépend que de celles qui la précèdent ; les réactions en sens inverse passent par des signaux, par exemple l'anonymisation RGPD ou le retrait d'un avis quand un voyage est annulé). Les **vues et gabarits** peuvent assembler plusieurs applications (par exemple la note moyenne affichée dans le catalogue).

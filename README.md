# Application_de_Voyages

Application web (Python 3, Django 5.2) pour une agence de voyage. Elle gère les comptes des clients et du personnel, et propose un catalogue de pays, destinations et activités. Le cahier des charges est résumé dans [Recap.md](Recap.md).

## Sommaire

- [Démarrage rapide](#démarrage-rapide)
- [Guide d'utilisation](#guide-dutilisation)
- [Fonctionnalités par rôle](#fonctionnalités-par-rôle)
- [Règles de gestion appliquées](#règles-de-gestion-appliquées)
- [Tests](#tests)
- [Mise en production](#mise-en-production)
- [Structure du code](#structure-du-code)

## Démarrage rapide

Prérequis : Python 3.10 ou plus récent.

```bash
pip install -r trip_app/requirements.txt
copy .env.example .env               # puis remplissez .env (voir ci-dessous)
cd trip_app
python manage.py migrate
python manage.py createsuperuser   # compte administrateur (la gérante)
python manage.py runserver
```

Ouvrez ensuite http://127.0.0.1:8000/ et connectez-vous avec le compte administrateur.

### Le fichier `.env` (réglages et secrets)

Les réglages se trouvent dans le fichier **`.env`**, à la racine du dépôt, créé à partir du modèle [.env.example](.env.example) où chaque réglage est expliqué. Il contient des secrets : il **n'est jamais commité** (protégé par `.gitignore`) et ne doit pas être partagé. Au minimum, renseignez `DJANGO_SECRET_KEY` (commande de génération indiquée dans le modèle). Les variables d'environnement définies dans Windows ou sur le serveur restent prioritaires sur ce fichier.

Pour **recevoir vraiment les e-mails** (Outlook / Hotmail) : dans `.env`, renseignez `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` (mot de passe d'application si la validation en deux étapes est activée) et `DJANGO_DEFAULT_FROM_EMAIL` (même adresse), puis passez `DJANGO_EMAIL_BACKEND` sur `django.core.mail.backends.smtp.EmailBackend`. Vérifiez avec `python manage.py sendtestemail votre@adresse`.

### Données de démonstration (facultatif)

Pour essayer l'application sans tout saisir :

```bash
python manage.py load_demo
```

La commande crée :

- 3 pays **fictifs** dont le nom commence par « Exemple — ». Leurs langue, monnaie et description sont inventées : ce ne sont **pas** de vraies informations de voyage. L'un des pays est désactivé, pour montrer ce que voient les clients.
- Un compte client `client.demo@example.com` et un compte agent `agent.demo@example.com`. Leurs mots de passe sont générés au hasard et **affichés dans le terminal** : notez-les.

La commande refuse de s'exécuter en production (`DJANGO_DEBUG=0`). Elle peut être relancée sans créer de doublons.

### E-mails en développement

En développement, aucun e-mail n'est réellement envoyé : il s'affiche dans le terminal où tourne `runserver`. C'est le cas des liens « mot de passe oublié » et des liens d'activation des agents. Copiez le lien affiché dans le navigateur.

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
| Décalage horaire (été / hiver) | Heures par rapport à la Belgique, par quart d'heure : `5.5`, `-6`, `5.75` |
| Période idéale | Mois de début et mois de fin ; peut chevaucher l'année (novembre → mars). Facultative |
| Durée d'une activité | En minutes : `90` pour 1 h 30 |
| Photo | Fichier JPEG, PNG ou WebP de 5 Mo maximum, envoyé depuis l'ordinateur. Facultative ; une nouvelle photo remplace l'ancienne |
| Prix | En euros. Le prix « à partir de » d'une destination est facultatif |

### Gérer les clients (agent ou administrateur)

1. Menu **Clients** : liste par pages de 25, avec recherche par nom, prénom ou e-mail (sans tenir compte des accents).
2. **Corriger** permet de modifier le prénom, le nom, le téléphone et la date de naissance. L'e-mail et le mot de passe restent gérés par le client.
3. **Envoyer un lien de mot de passe** : le client reçoit un lien valable 1 heure pour choisir un nouveau mot de passe. L'agent ne voit jamais le mot de passe.

### Utiliser l'application (client)

1. **Créer un compte** : remplissez le formulaire (sans mot de passe) et acceptez la politique de confidentialité. Un e-mail contient un lien, valable 24 heures, pour confirmer l'adresse et **choisir le mot de passe** ; le compte est alors activé. Rien reçu ? « Renvoyer l'e-mail de confirmation » depuis la page de connexion. Le téléphone est facultatif ; s'il est rempli, il doit être un numéro belge.
2. **Nos pays** : la liste des pays par continent est visible par tous. Le détail des pays, destinations et activités demande d'être connecté.
3. **Rechercher** : recherche par mot-clé (sans tenir compte des accents) et filtres. Un filtre ne s'applique qu'au type de résultat qu'il concerne :

   | Filtre | S'applique à |
   |---|---|
   | Continent | Pays, destinations et activités |
   | Budget maximum | Destinations (prix « à partir de » ; une destination sans prix reste affichée) et activités (prix par personne) |
   | Mois de voyage | Destinations dont la période idéale inclut ce mois |
   | Catégorie, difficulté, âge du voyageur | Activités |

4. **Favoris** : le bouton « Ajouter à mes favoris » se trouve sur la page d'une destination ou d'une activité. Retrouvez-les dans **Mes favoris**. Un favori devenu indisponible y reste signalé et peut être retiré.
5. **Mon profil** : modifier ses informations, changer son mot de passe ou **supprimer son compte**. La suppression est définitive et efface aussi les favoris.

### Mot de passe oublié

Sur la page de connexion, **Mot de passe oublié ?** envoie un lien valable 1 heure (3 demandes par heure au plus pour une même adresse, contre les envois en masse).

Limites par adresse IP, contre les robots : 20 échecs de connexion par 15 minutes, 5 inscriptions et 10 demandes de lien par heure. Elles sont volontairement larges, car un bureau ou un wifi partage souvent une même IP. Après 5 tentatives de connexion échouées, la connexion est bloquée 15 minutes pour cette adresse e-mail.

## Fonctionnalités par rôle

| Rôle | Fonctionnalités |
|---|---|
| Visiteur | Liste des pays par continent ; inscription ; connexion |
| Client | Détail des pays, destinations et activités ; recherche et filtres ; favoris ; profil (modifier, changer le mot de passe, supprimer le compte) |
| Agent | Consultation et recherche ; gestion du catalogue ; liste des clients, correction de leurs informations (sauf e-mail et mot de passe), envoi d'un lien de mot de passe ; profil (consultation, changement du mot de passe) |
| Administrateur | Droits de l'agent + gestion du personnel |

## Règles de gestion appliquées

- Un compte = une adresse e-mail unique, sans tenir compte des majuscules.
- Mots de passe hachés (jamais stockés en clair) : au moins 12 caractères, avec au moins une lettre et un chiffre. Les mots de passe trop courants ou trop proches du nom ou de l'e-mail sont refusés.
- Un nom de pays est unique, sans tenir compte des majuscules ni des accents (« Perou » = « Pérou »).
- Un client ne voit jamais les données d'un autre client ni celles du personnel. Les agents ne voient pas les favoris des clients.
- RGPD : consentement enregistré à l'inscription, page [politique de confidentialité](trip_app/templates/privacy.html), suppression réelle du compte par le client.
- L'inscription ne révèle jamais si une adresse est déjà cliente : la page est identique et la propriétaire de l'adresse est prévenue par e-mail. Le mot de passe est choisi après confirmation, ce qui empêche de « réserver » le compte de quelqu'un d'autre.

> **À compléter avant la mise en ligne :** les mentions marquées « [À COMPLÉTER] » dans la politique de confidentialité (responsable du traitement, contact, durée de conservation).

## Tests

```bash
cd trip_app
python manage.py test
```

Les tests utilisent un hachage de mot de passe rapide pour aller plus vite. L'application, elle, garde un hachage sécurisé (PBKDF2).

## Mise en production

Réglez ces variables dans le `.env` du serveur, ou directement comme variables d'environnement chez l'hébergeur :

| Variable | Rôle | Défaut |
|---|---|---|
| `DJANGO_DEBUG` | `1` en développement, `0` en production | `1` |
| `DJANGO_SECRET_KEY` | Clé secrète longue et aléatoire (obligatoire si `DJANGO_DEBUG=0`) | clé de développement |
| `DJANGO_ALLOWED_HOSTS` | Noms de domaine autorisés, séparés par des virgules | vide |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` pour envoyer de vrais e-mails | console |
| `DJANGO_EMAIL_HOST` / `DJANGO_EMAIL_PORT` | Serveur SMTP | `localhost` / `587` |
| `DJANGO_EMAIL_HOST_USER` / `DJANGO_EMAIL_HOST_PASSWORD` | Identifiants SMTP | vides |
| `DJANGO_EMAIL_USE_TLS` | `1` pour chiffrer la connexion SMTP | `1` |
| `DJANGO_DEFAULT_FROM_EMAIL` | Expéditeur des e-mails | `ne-pas-repondre@localhost` |
| `DJANGO_SECURE_SSL_REDIRECT` | `1` pour rediriger HTTP vers HTTPS | `1` |
| `DJANGO_HSTS_SECONDS` | Durée HSTS en secondes (ex. `31536000`), à activer une fois le HTTPS validé | `0` |
| `DJANGO_NUM_PROXIES` | Nombre de serveurs intermédiaires (proxy) de confiance devant le site, pour retrouver l'IP réelle des visiteurs. Laisser `0` si le site est en accès direct : sinon une IP pourrait être falsifiée | `0` |

Avec `DJANGO_DEBUG=0`, les cookies de session et CSRF ne sont envoyés qu'en HTTPS. Vérifiez la configuration avec :

```bash
python manage.py check --deploy
python manage.py collectstatic
```

Points d'attention :

- Planifiez chaque jour `python manage.py purge_unconfirmed` (tâche planifiée Windows ou cron) : elle efface les inscriptions non confirmées depuis plus de 7 jours (RGPD).
- **Ne committez jamais** la clé secrète ni les identifiants SMTP.
- Les limites (5 échecs de connexion, 3 liens « mot de passe oublié » par heure) utilisent le cache Django, en mémoire par défaut. Avec plusieurs processus serveur, configurez un cache partagé.
- SQLite suffit pour le volume prévu (environ 1 000 clients).
- Les photos envoyées sont stockées dans `trip_app/media/` (hors git). En développement, Django les sert lui-même ; en production, configurez le serveur web pour servir ce dossier à l'adresse `/media/`, et sauvegardez-le avec la base.

## Structure du code

Le code (identifiants, fichiers, routes internes) est en anglais ; l'interface, les adresses visibles, les commentaires et la documentation sont en français.

```
trip_app/
├── config/                 # paramètres et routes du projet
├── common/                 # outils partagés entre applications (normalisation du texte)
├── accounts/               # comptes : utilisateurs, rôles, RGPD
│   ├── views/              # auth, profile, staff, clients (une responsabilité par module)
│   ├── services/           # règles métier : e-mails de lien, règles du personnel, limitation des connexions
│   ├── models.py · forms.py · validators.py · decorators.py · urls.py
│   └── tests/
├── catalog/                # catalogue : pays, destinations, activités, favoris
│   ├── views/              # browse, search, favorites, manage
│   ├── services/           # recherche et filtres
│   ├── management/commands/load_demo.py
│   ├── models.py · forms.py · validators.py · urls.py
│   └── tests/
├── templates/
│   ├── base.html · home.html · privacy.html · 403/404/500.html
│   ├── accounts/           # auth/ · profile/ · staff/ · clients/ · emails/
│   └── catalog/            # pages publiques, fragments _*.html, manage/
└── static/css/             # feuille de style (texte lisible, adaptée au mobile)
```

Règle de rangement : les **vues** ne font que recevoir la requête et afficher la page ; la logique réutilisable va dans **services/** ; un outil utilisé par plusieurs applications va dans **common/**.

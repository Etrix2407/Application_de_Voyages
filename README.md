# Application_de_Voyages

Application web (Python 3, Django) pour gérer les comptes des clients et des agents, ainsi qu'un catalogue de destinations et d'activités organisé par pays. Le cahier des charges est résumé dans [Recap.md](Recap.md).

## Structure

```
trip_app/
├── config/            # settings, urls
├── comptes/           # utilisateurs, inscription, profil, RGPD
├── catalogue/         # pays, destinations, activités
├── templates/         # gabarits HTML partagés
└── static/            # feuilles de style
```

## Installation

```bash
pip install -r trip_app/requirements.txt
cd trip_app
python manage.py migrate
python manage.py createsuperuser   # compte administrateur (la gérante)
python manage.py runserver
```

L'application est alors disponible sur http://127.0.0.1:8000/.

## Tests

```bash
cd trip_app
python manage.py test
```

## Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `DJANGO_DEBUG` | `1` en développement, `0` en production | `1` |
| `DJANGO_SECRET_KEY` | Clé secrète (obligatoire si `DJANGO_DEBUG=0`) | clé de développement |
| `DJANGO_ALLOWED_HOSTS` | Hôtes autorisés, séparés par des virgules | vide |
| `DJANGO_EMAIL_BACKEND` | Moteur d'envoi des e-mails | console (e-mails affichés dans le terminal) |
| `DJANGO_DEFAULT_FROM_EMAIL` | Expéditeur des e-mails | `ne-pas-repondre@localhost` |

## Sécurité des comptes

- Mots de passe hachés, 12 caractères minimum avec au moins une lettre et un chiffre.
- Lien « mot de passe oublié » valable 1 heure.
- Connexion bloquée 15 minutes après 5 échecs pour une même adresse e-mail. Le compteur utilise le cache Django (en mémoire par défaut) : en production avec plusieurs processus, configurer un cache partagé.

## Gestion du personnel

- L'administrateur (créé avec `createsuperuser`) gère le personnel depuis le menu « Personnel ».
- Un agent créé reçoit un e-mail avec un lien (valable 1 heure) pour choisir son mot de passe ; l'administrateur peut renvoyer un lien.
- L'administrateur peut modifier, promouvoir administrateur, rétrograder, désactiver, réactiver ou supprimer un membre du personnel, mais jamais son propre compte (il reste donc toujours un administrateur actif).

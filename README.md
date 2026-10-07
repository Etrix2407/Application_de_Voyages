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

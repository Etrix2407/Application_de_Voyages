# application de voyage — Projet

une application pour gérer les comptes des clients et des agents, ainsi qu'un catalogue de destinations et d'activités organisé par pay

## Structure

À la racine du dépôt : `README.md` (présentation complète du projet).

```
trip_app/
├── config/            # settings, urls
├── comptes/           # utilisateurs, inscription, profil, RGPD
├── catalogue/         # pays, destinations, activités
└── templates/
```

## technologie

python 3 
Django
sqLite pour la db

## Règles de contenu

- Pas de doublon 
- Ne jamais inventer ni modifier des faits (dates, postes, entreprises, chiffres, compétences). Si une information manque ou semble incohérente, poser la question.

## Règles de code

- Code simple et lisible, sans dépendance superflue.
- Ne pas ajouter de bibliothèque (UI, Markdown, état, etc.) sans demande explicite.
- Respecter les bonnes pratiques python ci-dessous.

## Workflow Git

- La branche `main` est protégée : ne jamais pousser directement dessus.
- Pour toute modification : créer une branche (`git checkout -b <nom-court>`), committer, pousser la branche, puis ouvrir une pull request.
- Messages de commit courts, à l'impératif, en français (ex. : « Ajoute la section compétences »).
- Un commit = un changement cohérent.
- Ne jamais utiliser `git push --force`, `git reset --hard` ni supprimer de branche distante.
- une branche = une feature
- Demander confirmation avant chaque commit et chaque push.
- Ne jamais committer de secrets, de clés API ou de données personnelles non destinées à être publiques (adresse postale complète, numéro de téléphone, etc.) sans validation.

## Avant de terminer une tâche

1. lance des test unitaire
2. Résumer brièvement ce qui a changé.

---

You are an expert in python , and scalable application development. You write functional, maintainable, performant, and accessible code following python best practices u can find them in ur skill.


## Templates

- Keep templates simple and avoid complex logic: prepare data in views, not in templates.
- Use Django template tags (`{% if %}`, `{% for %}`, `{% url %}`) and extend a shared `base.html`.
- Always include `{% csrf_token %}` in forms and rely on Django auto-escaping (no `|safe` on user data).
- Keep pages readable for an older audience: large text, high contrast, labelled form fields, mobile-friendly layout.

## Services

- Design services around a single responsibility

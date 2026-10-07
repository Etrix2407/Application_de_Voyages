## Synthèse de l'analyste (à valider par la cliente)

**Objectif :** une application pour gérer les comptes des clients et des agents, ainsi qu'un catalogue de destinations et d'activités organisé par pays.

**Utilisateurs et droits**

| Rôle | Création du compte | Droits principaux |
|---|---|---|
| Visiteur (non connecté) | – | Consulter le catalogue |
| Client | Auto-inscription | Consulter le catalogue, modifier son profil, supprimer son compte |
| Agent | Créé par un administrateur | Gérer pays, destinations et activités ; consulter la liste des clients ; corriger leurs informations (sauf mot de passe) |
| Administrateur (la gérante) | Créé en amont | Droits de l'agent + créer, désactiver les comptes agents |

**Règles de gestion**

1. Un compte = une adresse e-mail unique (clients comme agents).
2. Le mot de passe doit respecter un minimum de robustesse et être récupérable en cas d'oubli de plus il doit pas etre en clair.
3. Un pays contient plusieurs destinations ; une destination appartient à un seul pays.
4. Une activité est proposée dans un seul pays (destination précise optionnelle) ; un pays propose plusieurs activités.
5. Un pays ne peut pas être supprimé s'il contient des destinations ou des activités ; on peut le désactiver (il disparaît alors pour les clients).
6. Seuls les agents modifient le catalogue.
7. Un client ne voit jamais les données d'un autre client ni celles du personnel.

**Données à gérer**

- **Client :** nom, prénom, e-mail, mot de passe, téléphone, date de naissance.
- **Agent :** nom, prénom, e-mail professionnel, mot de passe, numéro d'employé, rôle.
- **Pays :** nom, continent, langue principale, monnaie, description, visa requis pour les Belges, décalage horaire, actif/inactif.
- **Destination :** nom, description, période idéale, prix indicatif « à partir de », photo, pays, actif/inactif.
- **Activité :** nom, description, catégorie (culture, détente, sport, gastronomie, aventure), durée, prix par personne, niveau de difficulté, âge minimum, pays, destination (optionnelle), actif/inactif.

**Fonctionnalités de consultation :** liste des pays, détail d'un pays (destinations + activités), recherche par mot, filtres par catégorie et budget.

**Contraintes :** interface lisible (public plutôt âgé), utilisable sur ordinateur et téléphone, en français, conformité RGPD, volume d'environ 1 000 clients.

**Hors périmètre (version 1) :** paiement, réservation, facturation, e-mails promotionnels, version néerlandaise, intervention du neveu.

**Points à confirmer :** catalogue visible sans connexion ; favoris ; lien activité-destination ; niveaux de droits des agents.

---

**C :** C'est exactement ça. Vous avez même retenu la mouette ! Reprenez un café, il en reste. Et si vous voyez mon neveu dans le couloir, dites-lui que je suis en réunion.

**A :** Je n'y manquerai pas. Je reviens vers vous cette semaine avec une maquette. Merci, Nadine.

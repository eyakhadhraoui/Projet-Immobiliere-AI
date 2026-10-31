# CLAUDE.md — Règles permanentes du projet

Ce fichier définit les règles que tout assistant (IA ou développeur) doit respecter
lorsqu'il intervient sur ce projet.

## 1. Contexte

- Projet : **application web immobilière** composée de plusieurs modules :
  - **« Gestion des annonces »** (terminé, entrées CRUD-001 à FRONT-004 du journal) : CRUD des annonces, photos,
    historique, site public et espace propriétaire ;
  - **« Gestion des utilisateurs »** (en cours, entrées USER-…) : comptes gérés par chaque utilisateur lui-même
    (inscription, connexion, profil, mot de passe, photo, suppression), rôles **client** et **proprietaire**,
    authentification JWT en cookies httpOnly avec protection CSRF. Une fonctionnalité d'IA viendra plus tard
    (profil créé à partir de la CIN, vérification du visage).
- Tant que les annonces ne sont pas reliées aux comptes (USER-002), elles utilisent `owner_id = 1`.
- Architecture :

  ```
  React + Vite (frontend/)  →  API REST JSON  →  Flask (backend/)  →  SQLite (dev) / MySQL (plus tard)
  ```

- Le backend utilise le pattern **Application Factory** :
  `backend/app/__init__.py` expose l'objet `db` (Flask-SQLAlchemy) et la fonction `create_app()`.
- Environnement : **Windows**, **PowerShell**, environnement virtuel Python dans `backend/venv`
  (activation : `backend\venv\Scripts\Activate.ps1`).

## 2. Règles de code

- **Python 3.14**.
- **Type hints** obligatoires sur les fonctions et méthodes.
- **Docstrings au format Google-style**.
- Organisation des routes en **Blueprints Flask**.
- Validation des données avec **Marshmallow 4**.
- **Aucune donnée sensible en dur** (clés secrètes, mots de passe, URL de base de données…) :
  tout doit être lu depuis le fichier `.env` (liste des variables dans `backend/.env.example`).
- **Données personnelles** : mots de passe uniquement hachés, jamais renvoyés ni journalisés ; le hash et le
  numéro de CIN complet ne sortent jamais de l'API (CIN masquée).
- Gestion des erreurs **400 / 404 / 500 renvoyées en JSON**.

## 3. Intégration à l'existant

- **Ne jamais recréer une nouvelle application Flask.**
- Toujours s'intégrer à la structure existante : utiliser `db` et `create_app()`
  de `backend/app/__init__.py`, et enregistrer les nouveaux Blueprints dans `create_app()`.

## 4. Vérification

- Après chaque tâche, **exécuter les tests ou une vérification réelle**
  (ex. `pytest`, requête HTTP sur l'API, lancement du serveur).
- **Ne jamais prétendre qu'un test passe sans l'avoir réellement lancé.**
- **Lancer pytest depuis `backend/`** (venv activé) : `pytest.ini` s'y trouve et définit `pythonpath = .`.
  Lancé depuis la racine du projet, pytest échoue avec `ModuleNotFoundError: No module named 'app'`.

## 5. Journal des prompts

Après chaque tâche, ajouter une entrée à `docs/journal-prompts.md` contenant :

| Champ | Description |
|---|---|
| Identifiant | Code unique de la tâche (ex. `CRUD-001`) |
| Date | Date de réalisation (AAAA-MM-JJ) |
| Prompt exact reçu | Copie intégrale du prompt |
| Fichiers créés/modifiés | Liste des chemins |
| Commandes exécutées | Commandes lancées pendant la tâche |
| Résultat réel obtenu | Succès ou erreur, tel qu'observé |
| Corrections effectuées | Ajustements apportés après erreur ou relecture |
| Statut | `terminé` / `partiel` / `en attente` |

## 6. Git

- **Ne jamais faire de commit ni de push Git.**
- L'étudiante fera les commits elle-même à la fin du projet.
- Se contenter de signaler les fichiers modifiés.

## 7. Processus

- **Ne jamais arrêter un processus que tu n'as pas lancé toi-même dans la session en cours ;
  en cas de doute, demander à l'étudiante.**

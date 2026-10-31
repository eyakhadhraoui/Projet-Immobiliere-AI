# AGENTS.md — Règles permanentes du projet (à lire avant toute tâche)

> Copier ce fichier à la RACINE du nouveau projet sous le nom `AGENTS.md`, puis remplacer les `<...>`.
> Les tâches détaillées de la fonctionnalité « contrôle de fiabilité des annonces » sont dans
> `docs/PROMPTS-FIABILITE-CODEX.md` (prompts 1 à 12, à donner un par un).

## 1. Contexte

- Projet : application web immobilière `Immo Annonces`. Modules existants : `annonces, comptes, locations, visites, transactions, réclamations, maintenance, historique, RAG documentaire et sécurité des connexions`.
- Nouvelle fonctionnalité : **contrôle de fiabilité des annonces**. À la publication, les photos sont comparées aux
  photos des annonces déjà publiques, même celles du même propriétaire; le texte et les caractéristiques sont comparés
  aux annonces des autres propriétaires. Les anomalies de prix et de surface
  sont détectées. Le résultat est un niveau, « aucun signal », « à surveiller » ou « à vérifier », qui donne une
  décision : publication normale, confirmation demandée ou mise en attente.
- Architecture :

  ```
  React + Vite (frontend/)  →  API REST JSON  →  Flask (backend/)  →  SQLite (dev) / MySQL (plus tard)
  ```

- Le backend utilise le pattern **Application Factory** : `backend/app/__init__.py` expose `db` (Flask-SQLAlchemy) et
  `create_app()`.
- Environnement : **Windows**, **PowerShell**, environnement virtuel Python dans `backend/venv`
  (activation : `backend\venv\Scripts\Activate.ps1`). Utiliser toujours `backend\venv\Scripts\python.exe`, jamais le
  Python du système.

## 2. Règles de code

- **Python 3.12 ou plus** (`3.12.10`), **type hints** obligatoires, **docstrings Google-style**.
- Routes en **Blueprints Flask**, validation avec **Marshmallow**, migrations avec **Flask-Migrate / Alembic**.
- **Aucune donnée sensible en dur** (clés, mots de passe, URL de base) : tout vient de `.env`, avec la liste des
  variables dans `backend/.env.example`.
- **Données personnelles** : mots de passe uniquement hachés, jamais renvoyés ni journalisés, jamais écrits dans le
  code, le journal ou les captures.
- Erreurs **400 / 403 / 404 / 409 / 500 renvoyées en JSON**.
- Frontend : React, composants fonctionnels, couleurs uniquement par **variables CSS** (thèmes clair et sombre,
  contraste ≥ 4,5:1), sélecteurs accessibles (rôles et libellés) dans les tests.
- Sorties en ligne de commande affichables dans la console Windows (cp1252) : éviter « → », « ↔ » et « ≥ » dans les
  commandes Flask.

## 3. Intégration à l'existant

- **Ne jamais recréer une nouvelle application Flask** : utiliser `db` et `create_app()`, et enregistrer chaque nouveau
  Blueprint et chaque nouvelle commande dans `create_app()`.
- Avant de coder, lire le code concerné et respecter ses noms, son style et sa densité de commentaires.
- **Sauvegarder la base avant toute migration** (copie dans `backend/instance/sauvegardes/`) et vérifier la sauvegarde.

## 4. Règles propres au contrôle de fiabilité

- **Aucune API d'IA externe.** Les modèles tournent en local, sur processeur. Le modèle
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` est téléchargé UNE fois dans `backend/modeles/`
  (ignoré par Git), puis chargé hors ligne (`HF_HUB_OFFLINE=1`, `local_files_only=True`).
- Les bibliothèques d'IA sont **facultatives** (`backend/requirements-ia.txt`). Sans elles, le contrôle se replie
  automatiquement sur TF-IDF et l'application fonctionne.
- **Vocabulaire prudent** : on parle d'indices sur une ANNONCE, jamais d'un jugement sur une personne. Les mots
  « fraude », « fraudeur », « vol », « arnaque » et « suspect » ne doivent jamais apparaître dans l'interface. Les
  messages au propriétaire se terminent par « Ce contrôle automatique peut se tromper. » quand c'est prévu.
- **Aucune sanction contre une personne** : les signaux de texte, prix et caractéristiques ne sont que des avis ou une
  mise en attente révisable. Règle métier prioritaire : une photo détectée comme déjà utilisée dans une autre annonce
  ne peut jamais être publiée ni validée par confirmation ou modération; elle doit être retirée ou remplacée.
- **Confidentialité** :
  - le propriétaire ne voit jamais l'identifiant d'une annonce d'un autre propriétaire : seulement « une autre
    annonce », ou le titre et le lien si elle est PUBLIQUE ;
  - les empreintes des photos (SHA-256, pHash) et le contrôle complet ne sortent jamais de l'API ;
  - le site public n'affiche rien sur la fiabilité.
- **Méthode** :
  - tout seuil se règle sur l'ensemble de **validation**, jamais sur le test, qui ne sert qu'une fois ;
  - **ne jamais modifier un seuil** sans demande explicite ;
  - **n'inventer aucun chiffre** : chaque résultat vient d'une commande réellement lancée.
- Les décisions de modèle déjà prises (`decision_production` dans `seuils.json`) ne sont jamais remplacées sans l'option
  explicite prévue (`--remplacer-decision`).

## 5. Vérification

- Après chaque tâche, **lancer réellement** les tests et montrer leur sortie :
  - backend : `pytest -v` depuis `backend/`, venv activé. `pytest.ini` s'y trouve et définit `pythonpath = .` ;
    lancé depuis la racine, pytest échoue avec `ModuleNotFoundError: No module named 'app'` ;
  - frontend : `npm test`, `npm run lint`, `npm run build` dans `frontend/`.
- **Ne jamais prétendre qu'un test passe sans l'avoir lancé.** Tous les tests existants doivent continuer de passer.
- Pour toute règle importante, faire un **test de mutation** : modifier la règle exprès, vérifier qu'un test échoue,
  puis restaurer le fichier à l'identique et vérifier son empreinte.
- Enregistrer la sortie complète de `pytest -v` dans `docs/sorties/<IDENTIFIANT>-pytest.txt`.
- Validation de bout en bout : `python -m tests.e2e.demo_fiabilite` (Playwright), lancé depuis `backend/`, dans un
  environnement isolé : copie de la base, ports 5055 et 5174, uploads temporaires.

## 6. Journal des prompts

Après chaque tâche, ajouter une entrée à la FIN de `docs/journal-prompts.md`, **sans jamais modifier les entrées
précédentes** :

| Champ | Description |
|---|---|
| Identifiant | Code unique de la tâche (ex. `FIAB-001`) |
| Date | Date de réalisation (AAAA-MM-JJ) |
| Prompt exact reçu | Copie intégrale du prompt |
| Fichiers créés/modifiés | Liste des chemins |
| Commandes exécutées | Commandes lancées pendant la tâche |
| Résultat réel obtenu | Succès ou erreur, tel qu'observé (sorties réelles) |
| Corrections effectuées | Ajustements apportés après erreur ou relecture |
| Statut | `terminé` / `partiel` / `en attente` / `en attente de confirmation` |

## 7. Git

- **Ne jamais faire de commit ni de push.** L'étudiante fera les commits elle-même à la fin du projet.
- Se contenter de signaler les fichiers modifiés.
- Ne jamais versionner : `.env`, `backend/venv/`, `node_modules/`, `backend/instance/` (bases SQLite),
  `backend/uploads/`, `backend/modeles/` (modèles d'IA).

## 8. Processus

- **Ne jamais arrêter un processus qu'on n'a pas lancé soi-même** dans la session en cours (serveurs de l'étudiante sur
  les ports 5000 et 5173). En cas de doute, demander.
- Les serveurs de test lancés pour une vérification utilisent d'autres ports (5055, 5174) et sont arrêtés à la fin,
  uniquement eux.

## 9. Façon de travailler

- Raisonner étape par étape : inspecter d'abord (lecture seule), puis proposer, puis modifier.
- Quand une étape échoue, ne pas corriger l'application en silence : décrire l'échec (étape, attendu, observé, cause
  probable) et proposer une correction.
- Quand une demande est ambiguë ou qu'une décision appartient à l'étudiante (changer un modèle, un seuil, un message),
  proposer et **attendre sa confirmation**.
- Réponses en français, avec : fichiers modifiés, sortie réelle des tests, ce qui reste à faire.


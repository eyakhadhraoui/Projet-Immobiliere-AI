# Jeu annoté — contrôle de fiabilité (FIAB-002)

**Aucune annonce de ce dossier n'est réelle.**

- `annonces_sources.json` : 48 biens **fictifs rédigés par l'assistant d'IA (Claude Code)**, répartis en 16 groupes de 3 biens **différents** de même ville, même type et même transaction (paires difficiles). Chaque bien a une description et une **paraphrase** décrivant le même bien.
- `jeu_annote.json` et `photos/` sont **générés** par `app.ia.fiabilite.jeu.construire_jeu` (commande `flask --app run evaluer-fiabilite --regenerer`) :
  - 3 annonces par bien : `original`, `paraphrase` (ville orthographiée autrement, surface et prix légèrement modifiés, photo recadrée, redimensionnée ou éclaircie), `republication` (même texte à la casse et à la ponctuation près, photo copiée ou ré-enregistrée en JPEG) ;
  - 90 annonces `[DÉMO]` générées par `donnees_demo` : descriptions sur un même gabarit, utilisées **seulement comme non-doublons supplémentaires** ;
  - photos **synthétiques** (formes géométriques tirées avec une graine) : ce ne sont pas des photos de biens ;
  - anomalies injectées : prix ×10, ÷10, prix de l'autre transaction, surface ×10, ÷10, pièces incohérentes.
- Séparation **par groupe de biens** : entraînement (6 groupes, réservé au fine-tuning LoRA de FIAB-003), validation (5 groupes, réglage des seuils), test (5 groupes, mesure finale). Toutes les variantes et anomalies d'un bien restent dans son ensemble (`verifier_separation`).

Étiquettes : « doublon probable » (même bien source) et « anomalie » (valeur injectée). Ce sont des indices sur une annonce, jamais un jugement sur la personne qui la publie.

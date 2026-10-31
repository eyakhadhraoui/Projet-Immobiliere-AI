from app.ia.organisateur_litige import classer_passage, rapport_dossier


def test_classer_passage_identifie_theme_et_attribution_prudente():
    resultat = classer_passage("Je conteste la retenue de caution pour le sol. Message du 02/03/2026.")

    assert "depot" in resultat["sujets"]
    assert resultat["auteur_attribue"] == "locataire"
    assert resultat["dates"] == ["02/03/2026"]


def test_classer_passage_utilise_le_nom_de_fichier_et_reconnait_date_en_lettres():
    resultat = classer_passage("La retenue concerne les charges du logement. 5 octobre 2026.", "message_proprietaire.pdf")

    assert "charges" in resultat["sujets"]
    assert resultat["auteur_attribue"] == "proprietaire"
    assert resultat["auteur_methode"] == "nom du fichier"
    assert "05/10/2026" in resultat["dates"]


def test_rapport_retrouve_les_sources_et_trie_les_dates():
    documents = [{"nom": "messages.pdf", "passages": [
        {"texte": "Le propriétaire retient le dépôt pour les dégâts du sol, le 2026-02-12.",
         "source": "messages.pdf", "page": 2, "dates": ["2026-02-12"], "types": ["correspondance"],
         "sujets": ["depot"], "auteur_attribue": None},
        {"texte": "Je conteste la retenue pour le sol. 05/02/2026.", "source": "messages.pdf", "page": 1,
         "dates": ["05/02/2026"], "types": ["declaration"], "sujets": ["depot"], "auteur_attribue": "locataire"},
    ]}]

    rapport = rapport_dossier("Dépôt", documents, "retenue sol")

    assert [item["date"] for item in rapport["chronologie"]] == ["05/02/2026", "2026-02-12"]
    assert rapport["resultats"][0]["source"] == "messages.pdf"
    assert rapport["comptes_parties"][0]["auteur"] == "locataire"
    assert "ne détermine pas" in rapport["limite"]


def test_api_dossier_est_prive_par_compte(client_proprietaire, client_autre_proprietaire):
    cree = client_proprietaire.post("/api/dossiers-litige", json={"nom": "Dépôt"})
    assert cree.status_code == 201
    identifiant = cree.get_json()["id"]

    assert client_proprietaire.get(f"/api/dossiers-litige/{identifiant}/rapport").status_code == 200
    assert client_autre_proprietaire.get(f"/api/dossiers-litige/{identifiant}/rapport").status_code == 404

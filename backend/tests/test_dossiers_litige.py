"""Tests du stockage privé et du traitement documentaire local des dossiers de litige."""

from __future__ import annotations

from io import BytesIO

from app.ia.litiges.analyse import extraire_dates, repondre, valider_citation


def _creer_case(client, title="Retenue du dépôt"):
    response = client.post("/api/dossiers-litige", json={"titre": title, "description": "Analyse factuelle"})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _ajouter_txt(client, case_id, filename, text, role="unknown"):
    return client.post(
        f"/api/dossiers-litige/{case_id}/documents",
        data={"fichier": (BytesIO(text.encode("utf-8")), filename), "role_auteur": role},
        content_type="multipart/form-data",
    )


def test_dates_explicites_normalisees_et_dates_invalides_ignorees():
    dates = extraire_dates("Le bail débute le 2026-02-03. Email daté du 31/02/2026. Reçu le 5 October 2026. Voir aussi 05/06/2026.")
    assert [item["date"].isoformat() for item in dates] == ["2026-02-03", "2026-10-05"]
    assert all(item["verified"] is False for item in dates)
    assert "2026-02-03" in dates[0]["source_text"]


def test_citation_litterale_et_rejet_citation_inventee():
    source = "Le loyer mensuel est de 900 TND selon le bail."
    assert valider_citation(source, "900 TND")
    assert not valider_citation(source, "Le loyer a été payé")


def test_question_definition_retourne_reponse_courte_et_citation_exacte():
    source = (
        "Index des documents sources. D1 Inventaire d'entree signe. "
        "L'inventaire de l'etat des lieux d'entree mentionne une rayure sur le sol de la chambre. "
        "Les deux parties ont signe ce rapport d'etat. D2 Extrait du bail."
    )
    result = repondre("C'est quoi un inventaire d'entree signe ?", [{
        "texte": source,
        "chunk_id": "chunk-demo",
        "nom_fichier": "dossier.pdf",
    }])

    assert result["answer_status"] == "supported"
    assert "rapport d\u2019\u00e9tat des lieux" in result["answer"]
    assert "rayure" in result["answer"]
    assert "signe ce rapport" in result["answer"]
    assert len(result["citations"]) <= 3
    assert all(len(item["quote"]) < 250 for item in result["citations"])
    assert all(item["quote"] in source for item in result["citations"])


def test_api_dossier_documents_prives_et_dedoublonnage(client_proprietaire, client_autre_proprietaire, tmp_path):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    text = "Le bail prévoit un loyer mensuel de 900 TND. Signé le 2026-01-15."

    imported = _ajouter_txt(client_proprietaire, case_id, "bail.txt", text)
    assert imported.status_code == 201, imported.get_json()
    metadata = imported.get_json()["document"]
    assert metadata["passages"] == 1

    details = client_proprietaire.get(f"/api/dossiers-litige/{case_id}").get_json()
    passage = details["documents"][0]["passages"][0]
    assert passage["texte"] == text
    assert passage["debut"] == 0 and passage["fin"] == len(text)
    assert passage["needs_review"] is True
    assert "2026-01-15" in passage["dates"]

    stored = client_proprietaire.get(f"/api/dossiers-litige/{case_id}/documents/{metadata['id']}/fichier")
    assert stored.status_code == 200
    assert stored.data.decode("utf-8") == text
    assert _ajouter_txt(client_proprietaire, case_id, "copie.txt", text).status_code == 409

    assert client_autre_proprietaire.get(f"/api/dossiers-litige/{case_id}").status_code == 404
    assert client_autre_proprietaire.get(f"/api/dossiers-litige/{case_id}/documents/{metadata['id']}/fichier").status_code == 404
    assert client_autre_proprietaire.delete(f"/api/dossiers-litige/{case_id}").status_code == 404


def test_question_citee_et_abstention_pour_remboursement_non_prouve(client_proprietaire):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    source = "Reçu : versement initial du dépôt de garantie de 1 000 TND le 2026-01-15."
    assert _ajouter_txt(client_proprietaire, case_id, "recu.txt", source, "payment_provider").status_code == 201

    response = client_proprietaire.post(f"/api/dossiers-litige/{case_id}/questions", json={
        "question": "Quel montant de remboursement du dépôt est prouvé ?"
    })
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()
    assert answer["answer_status"] == "insufficient_evidence"
    assert answer["value"] is None
    assert answer["citations"] == []


def test_question_repond_avec_citation_exacte_et_rapport_exportable(client_proprietaire):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    source = "Le bail prévoit un loyer mensuel de 900 TND."
    upload = _ajouter_txt(client_proprietaire, case_id, "bail.txt", source)
    assert upload.status_code == 201

    answer_response = client_proprietaire.post(f"/api/dossiers-litige/{case_id}/questions", json={
        "question": "Quel montant de loyer prévoit le bail ?"
    })
    answer = answer_response.get_json()
    assert answer_response.status_code == 200
    assert answer["answer_status"] == "supported"
    assert answer["value"] == "900 TND"
    assert "900 TND" in answer["answer"]
    assert answer["citations"][0]["quote"] in source
    assert answer["citations"][0]["document_id"] == str(upload.get_json()["document"]["id"])
    assert answer["retrieval"]["mode"] == "tfidf_local"

    for format_ in ("json", "markdown", "html", "csv"):
        created = client_proprietaire.post(f"/api/dossiers-litige/{case_id}/reports", json={"format": format_})
        assert created.status_code == 201
        downloaded = client_proprietaire.get(created.get_json()["download_url"])
        assert downloaded.status_code == 200
        assert downloaded.data
        if format_ == "html":
            assert b"Rapport du dossier locatif" in downloaded.data


def test_question_signale_deux_positions_opposees_sans_choisir_la_version(client_proprietaire):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    landlord = "La marque du mur est apparue pendant la location; je retiens le dépôt."
    tenant = "Je conteste la retenue du dépôt. La marque était déjà présente à l'entrée."
    assert _ajouter_txt(client_proprietaire, case_id, "proprietaire.txt", landlord, "landlord").status_code == 201
    assert _ajouter_txt(client_proprietaire, case_id, "locataire.txt", tenant, "tenant").status_code == 201

    response = client_proprietaire.post(f"/api/dossiers-litige/{case_id}/questions", json={
        "question": "Les parties sont-elles d'accord sur la marque du mur et la retenue du dépôt ?"
    })
    result = response.get_json()
    assert response.status_code == 200
    assert result["answer_status"] == "conflicting_accounts"
    assert len(result["citations"]) == 2
    assert landlord in [item["quote"] for item in result["citations"]]
    assert tenant in [item["quote"] for item in result["citations"]]


def test_import_refuse_format_non_supporte_et_fichier_vide(client_proprietaire):
    case_id = _creer_case(client_proprietaire)["case_id"]
    bad_type = client_proprietaire.post(
        f"/api/dossiers-litige/{case_id}/documents",
        data={"fichier": (BytesIO(b"not an image"), "image.jpg")}, content_type="multipart/form-data",
    )
    assert bad_type.status_code == 400
    empty = client_proprietaire.post(
        f"/api/dossiers-litige/{case_id}/documents",
        data={"fichier": (BytesIO(b""), "vide.txt")}, content_type="multipart/form-data",
    )
    assert empty.status_code == 400


def test_recherche_ne_consulte_que_le_dossier_demande(client_proprietaire):
    case_a = _creer_case(client_proprietaire, "Bail A")
    case_b = _creer_case(client_proprietaire, "Bail B")
    assert _ajouter_txt(client_proprietaire, case_a["case_id"], "a.txt", "OMEGA_DOC_XYZA paiement reçu unique.").status_code == 201
    assert _ajouter_txt(client_proprietaire, case_b["case_id"], "b.txt", "ALPHA_DOC_QWERTY contrat unique.").status_code == 201

    result = client_proprietaire.post(f"/api/dossiers-litige/{case_a['case_id']}/search", json={
        "question": "ALPHA_DOC_QWERTY"
    })
    assert result.status_code == 200
    assert result.get_json()["items"] == []


def test_evidence_accounts_and_timeline_stay_case_scoped(client_proprietaire, client_autre_proprietaire):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    statement = "Je conteste la retenue sur le dépôt, le 5 octobre 2026."
    assert _ajouter_txt(client_proprietaire, case_id, "locataire.txt", statement, "tenant").status_code == 201

    accounts = client_proprietaire.get(f"/api/dossiers-litige/{case_id}/accounts").get_json()
    assert accounts["items"]["tenant"]
    assert accounts["items"]["tenant"][0]["status"] == "déclaration non authentifiée"
    timeline = client_proprietaire.get(f"/api/dossiers-litige/{case_id}/timeline").get_json()
    assert timeline["items"][0]["date"] == "2026-10-05"
    assert timeline["items"][0]["verified"] is False
    assert client_autre_proprietaire.get(f"/api/dossiers-litige/{case_id}/timeline").status_code == 404
    assert client_autre_proprietaire.get(f"/api/dossiers-litige/{case_id}/evidence").status_code == 404


def test_creation_dossier_litige_rattache_contrat_location(client_proprietaire, annonce_valide):
    annonce = client_proprietaire.post("/api/annonces", json=annonce_valide)
    assert annonce.status_code == 201
    contrat = client_proprietaire.post("/api/locations", json={
        "annonce_id": annonce.get_json()["id"], "locataire_id": 1,
        "date_debut": "2026-01-01", "date_fin": "2026-12-31",
        "loyer_mensuel": 900,
    })
    assert contrat.status_code == 201
    assert client_proprietaire.put(
        f"/api/locations/{contrat.get_json()['id']}", json={"contrat_pdf": "bail.pdf"}
    ).status_code == 200

    dossier = client_proprietaire.post("/api/dossiers-litige", json={
        "titre": "Litige lié au bail", "location_id": contrat.get_json()["id"],
    })

    assert dossier.status_code == 201
    assert dossier.get_json()["location"] == {
        "id": contrat.get_json()["id"],
        "reference": contrat.get_json()["reference"],
        "annonce_id": annonce.get_json()["id"],
        "date_debut": "2026-01-01",
        "date_fin": "2026-12-31",
        "statut": "active",
        "contrat_disponible": True,
    }


def test_creation_dossier_litige_refuse_location_d_un_autre_utilisateur(
    client_proprietaire, client_autre_proprietaire, annonce_valide
):
    annonce = client_proprietaire.post("/api/annonces", json=annonce_valide)
    assert annonce.status_code == 201
    contrat = client_proprietaire.post("/api/locations", json={
        "annonce_id": annonce.get_json()["id"], "locataire_id": 1,
    })
    assert contrat.status_code == 201

    dossier = client_autre_proprietaire.post("/api/dossiers-litige", json={
        "titre": "Dossier non autorisé", "location_id": contrat.get_json()["id"],
    })

    assert dossier.status_code == 404


def test_filtre_inventaire_par_nom_auteur(client_proprietaire):
    case_id = _creer_case(client_proprietaire)["case_id"]
    response = client_proprietaire.post(
        f"/api/dossiers-litige/{case_id}/documents",
        data={"fichier": (BytesIO(b"Le paiement est mentionne."), "paiement.txt"),
              "auteur": "Prestataire Atlas", "role_auteur": "payment_provider"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert client_proprietaire.get(f"/api/dossiers-litige/{case_id}/evidence?author=atlas").get_json()["total"] == 1
    assert client_proprietaire.get(f"/api/dossiers-litige/{case_id}/evidence?author=autre").get_json()["total"] == 0


def test_suppression_dossier_efface_pieces_et_fichier_local(client_proprietaire):
    case = _creer_case(client_proprietaire)
    case_id = case["case_id"]
    assert _ajouter_txt(client_proprietaire, case_id, "note.txt", "Note du dossier.").status_code == 201
    # Le chemin de stockage est vérifié à travers la liste des documents et le endpoint privé.
    doc_id = client_proprietaire.get(f"/api/dossiers-litige/{case_id}").get_json()["documents"][0]["id"]
    file_url = f"/api/dossiers-litige/{case_id}/documents/{doc_id}/fichier"
    assert client_proprietaire.get(file_url).status_code == 200
    assert client_proprietaire.delete(f"/api/dossiers-litige/{case_id}").status_code == 200
    assert client_proprietaire.get(file_url).status_code == 404

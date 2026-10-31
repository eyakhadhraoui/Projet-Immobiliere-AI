"""Analyse de risque des connexions et vérification renforcée par e-mail."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import delete, select, or_
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.errors import IdentifiantsInvalides
from app.models import EvenementConnexion, Utilisateur, VerificationConnexion
from app.models.annonce import vers_utc

_CATEGORIES_NAVIGATEUR = (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
                          ("Safari/", "Safari"), ("OPR/", "Opera"))
_CODE_APPAREIL = {"inconnu": 0.0, "ordinateur": 0.0, "mobile": 1.0, "tablette": 2.0, "bot": 3.0}
_CODE_NAVIGATEUR = {"inconnu": 0.0, "Chrome": 1.0, "Firefox": 2.0, "Safari": 3.0,
                    "Edge": 4.0, "Opera": 5.0, "Autre": 6.0}


def empreinte(valeur: str | None) -> str | None:
    """Retourne une empreinte HMAC non réversible, sans conserver la valeur brute."""
    if not valeur:
        return None
    cle = str(current_app.config.get("JWT_SECRET_KEY") or current_app.secret_key).encode()
    return hmac.new(cle, valeur.encode("utf-8", "ignore"), hashlib.sha256).hexdigest()


def _agent(chaine: str | None) -> tuple[str, str]:
    chaine = (chaine or "")[:1000]
    navigateur = next((nom for marqueur, nom in _CATEGORIES_NAVIGATEUR if marqueur in chaine), "Autre")
    if "bot" in chaine.lower() or "crawler" in chaine.lower():
        appareil = "bot"
    elif "ipad" in chaine.lower() or "tablet" in chaine.lower():
        appareil = "tablette"
    elif any(m in chaine.lower() for m in ("mobile", "android", "iphone")):
        appareil = "mobile"
    else:
        appareil = "ordinateur"
    return navigateur, appareil


def _lieu_ip(adresse_ip: str | None) -> str | None:
    """Résout un lieu ville/pays via une base GeoIP locale, sans transmettre l'IP à un tiers."""
    if not adresse_ip:
        return None
    try:
        ip = ipaddress.ip_address(adresse_ip)
        if not ip.is_global:
            return "Réseau local"
        import geoip2.database
        chemin = Path(current_app.config.get("GEOIP_CITY_DB", ""))
        if not chemin.is_file():
            return None
        with geoip2.database.Reader(str(chemin)) as lecteur:
            resultat = lecteur.city(str(ip))
        ville = resultat.city.name
        pays = resultat.country.name
        return ", ".join(part for part in (ville, pays) if part) or None
    except (ValueError, OSError, ImportError, Exception) as erreur:
        # Les bases GeoIP ne couvrent pas toutes les adresses; l'authentification ne doit pas en dépendre.
        current_app.logger.debug("Lieu GeoIP indisponible: %s", erreur)
        return None


def _vecteur(heure: datetime, navigateur: str, appareil: str, echecs: int) -> list[float]:
    heure_locale = heure.astimezone(timezone.utc).hour + heure.minute / 60
    angle = 2 * 3.141592653589793 * heure_locale / 24
    return [__import__("math").sin(angle), __import__("math").cos(angle),
            _CODE_APPAREIL.get(appareil, 0.0), _CODE_NAVIGATEUR.get(navigateur, 6.0),
            min(echecs, 10) / 10.0]


def _modele_global() -> Any | None:
    """Charge le modèle entraîné ou en ajuste un provisoire si l'historique suffit."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        current_app.logger.warning("Scikit-learn absent; analyse des connexions par règles uniquement.")
        return None

    chemin = Path(current_app.config.get("MODELES_FOLDER", "modeles")) / "isolation_connexions.joblib"
    if chemin.is_file():
        try:
            import joblib
            return joblib.load(chemin)
        except (OSError, ValueError, EOFError):
            current_app.logger.warning("Modèle des connexions illisible; repli sur les règles.")
    evenements = db.session.scalars(select(EvenementConnexion).order_by(EvenementConnexion.heure_utc.desc()).limit(2000)).all()
    if len(evenements) < 30:
        return None
    return IsolationForest(n_estimators=120, contamination=0.06, random_state=42).fit([
        _vecteur(vers_utc(e.heure_utc), e.navigateur, e.appareil, 0 if e.reussie else 1)
        for e in evenements
    ])


def _risque(utilisateur_id: int, navigateur: str, appareil: str, ip_hash: str | None,
            heure: datetime) -> tuple[str, float, dict[str, bool]]:
    evenements = db.session.scalars(select(EvenementConnexion).where(
        EvenementConnexion.utilisateur_id == utilisateur_id
    ).order_by(EvenementConnexion.heure_utc.desc()).limit(200)).all()
    succes = [e for e in evenements if e.reussie]
    derniere = succes[0] if succes else None
    nouvel_appareil = bool(derniere and derniere.appareil != appareil)
    nouveau_navigateur = bool(derniere and derniere.navigateur != navigateur)
    nouvelle_ip = bool(derniere and ip_hash and derniere.ip_hash and derniere.ip_hash != ip_hash)
    echec_recents = sum(not e.reussie and (heure - vers_utc(e.heure_utc)) <= timedelta(hours=24) for e in evenements)
    heure_inhabituelle = heure.hour < 5 or heure.hour >= 23

    score = (0.35 * nouvel_appareil + 0.20 * nouveau_navigateur + 0.15 * nouvelle_ip
             + 0.35 * (echec_recents >= 2) + 0.10 * heure_inhabituelle)
    modele = _modele_global()
    anomalie_ml = bool(modele is not None and modele.predict(
        [_vecteur(heure, navigateur, appareil, echec_recents)]
    )[0] == -1)
    if anomalie_ml:
        score = max(score, 0.55)

    tres_suspecte = echec_recents >= 4 or (nouvel_appareil and echec_recents >= 2 and heure_inhabituelle)
    suspecte = tres_suspecte or anomalie_ml or score >= 0.45
    niveau = "tres_eleve" if tres_suspecte else "suspect" if suspecte else "faible"
    return niveau, min(float(score), 1.0), {
        "nouvel_appareil": nouvel_appareil, "nouveau_navigateur": nouveau_navigateur,
        "nouvelle_adresse": nouvelle_ip, "echecs_recents": echec_recents > 0,
        "anomalie_modele": anomalie_ml,
    }


def enregistrer_connexion(utilisateur: Utilisateur, adresse_ip: str | None, agent: str | None,
                          reussie: bool) -> dict[str, Any]:
    """Enregistre un succès ou un échec et calcule un score pour les succès."""
    maintenant = datetime.now(timezone.utc)
    navigateur, appareil = _agent(agent)
    ip_hash = empreinte(adresse_ip)
    if reussie:
        niveau, score, signaux = _risque(utilisateur.id, navigateur, appareil, ip_hash, maintenant)
    else:
        niveau, score, signaux = "faible", 0.0, {}
    evenement = EvenementConnexion(
        utilisateur_id=utilisateur.id, reussie=reussie, heure_utc=maintenant, navigateur=navigateur,
        appareil=appareil, lieu_approximatif=_lieu_ip(adresse_ip), ip_hash=ip_hash,
        niveau_risque=niveau, score_risque=score,
    )
    db.session.add(evenement)
    db.session.commit()
    return {"evenement_id": evenement.id, "niveau": niveau, "score": score, "signaux": signaux}


def enregistrer_echec_inconnu(adresse_ip: str | None, agent: str | None) -> None:
    """Conserve les échecs anonymes pour les tendances globales, sans enregistrer l'adresse e-mail."""
    navigateur, appareil = _agent(agent)
    db.session.add(EvenementConnexion(
        utilisateur_id=None, reussie=False, navigateur=navigateur, appareil=appareil,
        lieu_approximatif=_lieu_ip(adresse_ip),
        ip_hash=empreinte(adresse_ip),
    ))
    db.session.commit()


def enregistrer_echec(utilisateur_id: int | None, adresse_ip: str | None, agent: str | None) -> None:
    """Enregistre un échec sans stocker l'adresse e-mail utilisée."""
    navigateur, appareil = _agent(agent)
    db.session.add(EvenementConnexion(
        utilisateur_id=utilisateur_id, reussie=False, navigateur=navigateur, appareil=appareil,
        lieu_approximatif=_lieu_ip(adresse_ip),
        ip_hash=empreinte(adresse_ip),
    ))
    db.session.commit()


def envoyer_code(utilisateur: Utilisateur, code: str) -> None:
    """Envoie le code via SMTP configuré dans l'environnement."""
    config = current_app.config
    hote = config.get("MAIL_SERVER")
    expediteur = config.get("MAIL_DEFAULT_SENDER")
    if not hote or not expediteur:
        raise RuntimeError("Le serveur e-mail n'est pas configuré (MAIL_SERVER et MAIL_DEFAULT_SENDER).")
    message = EmailMessage()
    message["Subject"] = "Vérification de votre connexion Immo Annonces"
    message["From"] = expediteur
    message["To"] = utilisateur.email
    message.set_content(f"Votre code de vérification est : {code}\nIl expire dans 10 minutes.")
    port = int(config.get("MAIL_PORT", 587))
    if config.get("MAIL_USE_SSL"):
        with smtplib.SMTP_SSL(hote, port, context=ssl.create_default_context(), timeout=10) as smtp:
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
            smtp.send_message(message)
    else:
        with smtplib.SMTP(hote, port, timeout=10) as smtp:
            smtp.ehlo()
            if config.get("MAIL_USE_TLS", True):
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
            smtp.send_message(message)


def creer_verification(utilisateur: Utilisateur, evenement_id: int) -> str:
    """Crée et envoie un défi opaque, à usage unique et valable dix minutes."""
    jeton = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    defi = VerificationConnexion(
        jeton_hash=hashlib.sha256(jeton.encode()).hexdigest(), code_hash=generate_password_hash(code),
        utilisateur_id=utilisateur.id, evenement_id=evenement_id,
        expire_le=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.session.add(defi)
    db.session.commit()
    try:
        envoyer_code(utilisateur, code)
    except Exception:
        db.session.delete(defi)
        db.session.commit()
        raise
    return jeton


def valider_verification(jeton: str, code: str) -> Utilisateur:
    """Valide le code une seule fois; cinq erreurs consomment le défi."""
    empreinte_jeton = hashlib.sha256(jeton.encode()).hexdigest()
    defi = db.session.scalar(select(VerificationConnexion).where(VerificationConnexion.jeton_hash == empreinte_jeton))
    maintenant = datetime.now(timezone.utc)
    if (defi is None or defi.utilise_le is not None or vers_utc(defi.expire_le) <= maintenant
            or defi.nb_echecs >= 5):
        raise IdentifiantsInvalides()
    if not check_password_hash(defi.code_hash, code):
        defi.nb_echecs += 1
        db.session.commit()
        raise IdentifiantsInvalides()
    defi.utilise_le = maintenant
    utilisateur = db.session.get(Utilisateur, defi.utilisateur_id)
    if utilisateur is None:
        db.session.commit()
        raise IdentifiantsInvalides()
    evenement = db.session.get(EvenementConnexion, defi.evenement_id)
    if evenement:
        evenement.retour_utilisateur = "confirmee"
    db.session.commit()
    return utilisateur


def retour_evenement(utilisateur: Utilisateur, evenement_id: int, confirme: bool) -> None:
    """Enregistre le retour uniquement sur un événement du compte connecté."""
    evenement = db.session.scalar(select(EvenementConnexion).where(
        EvenementConnexion.id == evenement_id,
        EvenementConnexion.utilisateur_id == utilisateur.id,
        EvenementConnexion.reussie.is_(True),
    ))
    if evenement is None:
        raise IdentifiantsInvalides()
    evenement.retour_utilisateur = "confirmee" if confirme else "refusee"
    if not confirme:
        utilisateur.jeton_version += 1
    db.session.commit()


def alerte_recente(utilisateur: Utilisateur) -> dict[str, Any] | None:
    """Retourne la dernière alerte non traitée du compte, limitée aux sept derniers jours."""
    depuis = datetime.now(timezone.utc) - timedelta(days=7)
    evenement = db.session.scalar(select(EvenementConnexion).where(
        EvenementConnexion.utilisateur_id == utilisateur.id,
        EvenementConnexion.reussie.is_(True),
        EvenementConnexion.niveau_risque == "suspect",
        EvenementConnexion.retour_utilisateur.is_(None),
        EvenementConnexion.heure_utc >= depuis,
    ).order_by(EvenementConnexion.heure_utc.desc()))
    if evenement is None:
        return None
    return {
        "evenement_id": evenement.id,
        "message": "Une connexion inhabituelle a été détectée. Confirmez si vous en êtes à l’origine.",
        "date": vers_utc(evenement.heure_utc).isoformat(),
        "navigateur": evenement.navigateur,
        "appareil": evenement.appareil,
    }


def historique_connexions(utilisateur: Utilisateur, limite: int = 50) -> list[dict[str, Any]]:
    """Retourne uniquement les événements du compte connecté, sans IP ni empreinte."""
    evenements = db.session.scalars(select(EvenementConnexion).where(
        EvenementConnexion.utilisateur_id == utilisateur.id
    ).order_by(EvenementConnexion.heure_utc.desc()).limit(min(max(limite, 1), 100))).all()
    return [{
        "id": evenement.id,
        "date": vers_utc(evenement.heure_utc).isoformat(),
        "reussie": evenement.reussie,
        "navigateur": evenement.navigateur,
        "appareil": evenement.appareil,
        "lieu": evenement.lieu_approximatif or "Lieu non disponible",
        "risque": evenement.niveau_risque,
        "retour": evenement.retour_utilisateur,
    } for evenement in evenements]


def historique_connexions(utilisateur: Utilisateur, limite: int = 50) -> list[dict[str, Any]]:
    """Retourne uniquement les événements du compte connecté, sans IP ni empreinte."""
    evenements = db.session.scalars(select(EvenementConnexion).where(
        EvenementConnexion.utilisateur_id == utilisateur.id
    ).order_by(EvenementConnexion.heure_utc.desc()).limit(min(max(limite, 1), 100))).all()
    return [{
        "id": evenement.id,
        "date": vers_utc(evenement.heure_utc).isoformat(),
        "reussie": evenement.reussie,
        "navigateur": evenement.navigateur,
        "appareil": evenement.appareil,
        "lieu": evenement.lieu_approximatif or "Lieu non disponible",
        "risque": evenement.niveau_risque,
        "retour": evenement.retour_utilisateur,
    } for evenement in evenements]


def entrainer(dossier: str | Path) -> dict[str, int]:
    """Entraîne IsolationForest sur les événements stockés et sauvegarde le modèle local."""
    from sklearn.ensemble import IsolationForest
    import joblib

    evenements = db.session.scalars(select(EvenementConnexion).order_by(EvenementConnexion.heure_utc)).all()
    if len(evenements) < 30:
        raise ValueError(f"Il faut au moins 30 événements de connexion; {len(evenements)} disponible(s).")
    X = [_vecteur(vers_utc(e.heure_utc), e.navigateur, e.appareil, 0 if e.reussie else 1) for e in evenements]
    modele = IsolationForest(n_estimators=160, contamination=0.06, random_state=42).fit(X)
    destination = Path(dossier)
    destination.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, destination / "isolation_connexions.joblib")
    return {"evenements": len(X), "anomalies_apprentissage": int((modele.predict(X) == -1).sum())}


def evaluer() -> dict[str, int]:
    """Évalue le modèle sur une fenêtre récente avec taux d'anomalies et comparaison aux règles."""
    modele = _modele_global()
    if modele is None:
        raise ValueError("Au moins 30 événements sont requis avant l'évaluation.")
    evenements = db.session.scalars(select(EvenementConnexion).order_by(EvenementConnexion.heure_utc.desc()).limit(500)).all()
    X = [_vecteur(vers_utc(e.heure_utc), e.navigateur, e.appareil, 0 if e.reussie else 1) for e in evenements]
    anomalies = int((modele.predict(X) == -1).sum())
    regles = sum(e.niveau_risque in ("suspect", "tres_eleve") for e in evenements)
    return {"evenements_evalues": len(X), "anomalies_isolation_forest": anomalies, "alertes_regles": regles}


def nettoyer(retention_jours: int) -> int:
    """Efface les événements de ce module au-delà de la durée de conservation configurée."""
    limite = datetime.now(timezone.utc) - timedelta(days=max(1, retention_jours))
    vieux_defis = delete(VerificationConnexion).where(or_(
        VerificationConnexion.expire_le < datetime.now(timezone.utc),
        VerificationConnexion.utilise_le < limite,
    ))
    db.session.execute(vieux_defis)
    anciens = db.session.execute(delete(EvenementConnexion).where(EvenementConnexion.heure_utc < limite))
    db.session.commit()
    return int(anciens.rowcount or 0)

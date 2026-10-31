import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _chemin_backend(valeur: str) -> str:
    """Résout un chemin relatif par rapport au dossier ``backend/``.

    Args:
        valeur: Chemin absolu, ou relatif à ``backend/``.

    Returns:
        str: Chemin absolu.
    """
    chemin = Path(valeur)
    return str(chemin if chemin.is_absolute() else BACKEND_DIR / chemin)


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = _chemin_backend(os.getenv("UPLOAD_FOLDER", "uploads"))
    # Modèles d'IA entraînés localement (IA-ANNONCE-001) ; dossier non commité (.gitignore).
    MODELES_FOLDER = _chemin_backend(os.getenv("MODELES_FOLDER", "modeles"))
    DOSSIERS_LITIGE_FOLDER = _chemin_backend(os.getenv("DOSSIERS_LITIGE_FOLDER", "instance/dossiers_litige"))
    # Facultatif : répertoire d'un modèle déjà téléchargé. Le module ne contacte jamais Hugging Face.
    _litige_modele_local = os.getenv("DOSSIERS_LITIGE_MODELE_SEMANTIQUE", "").strip()
    DOSSIERS_LITIGE_MODELE_SEMANTIQUE = _chemin_backend(_litige_modele_local) if _litige_modele_local else None
    # 5 Mo par requête : limite générale des téléversements.
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(5 * 1024 * 1024)))
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    GEMINI_PHOTO_FALLBACK_MODEL = os.getenv(
        "GEMINI_PHOTO_FALLBACK_MODEL", "gemini-3.6-flash"
    ).strip() or "gemini-3.6-flash"
    GEMINI_MAINTENANCE_DIAGNOSTIC_FALLBACK_MODEL = os.getenv(
        "GEMINI_MAINTENANCE_DIAGNOSTIC_FALLBACK_MODEL", "gemini-3.6-flash"
    ).strip() or "gemini-3.6-flash"
    GEMINI_RECLAMATION_MODEL = os.getenv("GEMINI_RECLAMATION_MODEL", "").strip()
    GEMINI_RECLAMATION_FALLBACK_MODEL = os.getenv(
        "GEMINI_RECLAMATION_FALLBACK_MODEL", "gemini-3.6-flash"
    ).strip()
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "45"))
    RECLAMATIONS_LLM_PROVIDER = os.getenv("RECLAMATIONS_LLM_PROVIDER", "gemini").strip().lower()
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    OLLAMA_RECLAMATION_MODEL = os.getenv("OLLAMA_RECLAMATION_MODEL", "qwen2.5:3b").strip()
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    CONNEXION_RETENTION_JOURS = int(os.getenv("CONNEXION_RETENTION_JOURS", "180"))
    GEOIP_CITY_DB = _chemin_backend(os.getenv("GEOIP_CITY_DB", "geoip/GeoLite2-City.mmdb"))

    # Authentification (flask-jwt-extended). La clé est obligatoire : create_app() refuse de démarrer sans elle
    # (sinon la bibliothèque utiliserait SECRET_KEY à la place, sans prévenir).
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # Jetons uniquement en cookies httpOnly (illisibles par JavaScript) ; le frontend passe par le proxy Vite
    # (même origine), donc SameSite=Lax suffit et le CSRF est vérifié par double cookie (en-tête X-CSRF-TOKEN).
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = "Lax"
    # True en production (HTTPS) ; False en développement local (http://localhost).
    JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true"
    JWT_ACCESS_COOKIE_PATH = "/api/"
    JWT_REFRESH_COOKIE_PATH = "/api/auth/"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

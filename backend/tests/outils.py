"""Outils partagés des tests (module unique, importé par conftest.py et par les fichiers de test).

Les valeurs aléatoires doivent être générées ici, une seule fois : si les tests importaient
``tests.conftest``, Python chargerait conftest.py une seconde fois (pytest le charge déjà sous le nom
``conftest``) et chaque copie générerait son propre mot de passe (USER-002).
"""

from __future__ import annotations

import secrets
from typing import Any

from flask.testing import FlaskClient


def mot_de_passe_aleatoire() -> str:
    """Mot de passe conforme à la politique, généré à chaque exécution : aucun mot de passe n'est écrit
    dans le code des tests (USER-002).

    Returns:
        str: Mot de passe (lettres et chiffres, 20 caractères).
    """
    return f"Mdp{secrets.token_hex(8)}7"


MOT_DE_PASSE = mot_de_passe_aleatoire()  # mot de passe des comptes de test, différent à chaque exécution
MAUVAIS_MOT_DE_PASSE = mot_de_passe_aleatoire()  # valide selon la politique, mais pas celui du compte


class ClientNavigateur(FlaskClient):
    """Client de test qui joint l'en-tête X-CSRF-TOKEN aux requêtes modifiantes, comme le frontend."""

    def open(self, *args: Any, **kwargs: Any) -> Any:
        """Ajoute l'en-tête CSRF (cookie ``csrf_access_token``) aux requêtes POST / PUT / PATCH / DELETE.

        Args:
            *args: Arguments de ``FlaskClient.open``.
            **kwargs: Arguments nommés de ``FlaskClient.open``.

        Returns:
            Any: Réponse de test.
        """
        if str(kwargs.get("method", "GET")).upper() not in {"GET", "HEAD", "OPTIONS"}:
            cookie = self.get_cookie("csrf_access_token")
            if cookie is not None:
                entetes = dict(kwargs.pop("headers", None) or {})
                entetes.setdefault("X-CSRF-TOKEN", cookie.value)
                kwargs["headers"] = entetes
        return super().open(*args, **kwargs)


def entete_csrf(client: FlaskClient, rafraichissement: bool = False) -> dict[str, str]:
    """En-tête CSRF à joindre aux requêtes POST / PUT / DELETE authentifiées.

    Args:
        client: Client de test qui possède les cookies de session.
        rafraichissement: ``True`` pour ``/api/auth/rafraichir`` (cookie ``csrf_refresh_token``).

    Returns:
        dict[str, str]: ``{"X-CSRF-TOKEN": <valeur du cookie CSRF>}``.
    """
    cookie = client.get_cookie("csrf_refresh_token" if rafraichissement else "csrf_access_token")
    assert cookie is not None, "aucun cookie CSRF : le client n'est pas connecté"
    return {"X-CSRF-TOKEN": cookie.value}

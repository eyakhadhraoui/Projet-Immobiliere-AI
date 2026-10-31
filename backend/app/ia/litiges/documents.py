"""Extraction sûre des fichiers de preuve vers du texte avec offsets stables."""

from __future__ import annotations

import email
import hashlib
import html
import io
import json
import zipfile
from dataclasses import dataclass
from email import policy
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader


TAILLE_MAX_FICHIER = 4 * 1024 * 1024
TAILLE_MAX_TEXTE = 8_000_000
EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".eml", ".json"}
MIMES = {
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown",
    ".eml": "message/rfc822", ".json": "application/json",
}


@dataclass(frozen=True)
class PageText:
    """Texte extrait d'une page et offsets correspondants dans le texte global."""

    page: int | None
    start: int
    end: int


class _TexteHTML(HTMLParser):
    """Extrait du texte d'un courriel HTML sans interpréter son contenu."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        elif tag in {"p", "br", "div", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "div", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def extraire_document(contenu: bytes, nom: str) -> tuple[str, str, list[PageText], str]:
    """Valide un document puis extrait son texte sans effectuer d'appel réseau.

    Args:
        contenu: Octets du fichier envoyé.
        nom: Nom d'origine utilisé uniquement pour déterminer le format.

    Returns:
        Tuple texte, type MIME, pages, hash SHA-256.

    Raises:
        ValueError: Si le fichier est vide, trop lourd, invalide ou sans texte.
    """
    suffixe = Path(nom).suffix.lower()
    if suffixe not in EXTENSIONS:
        raise ValueError("Formats acceptés : PDF, DOCX, TXT, Markdown, EML et JSON.")
    if not contenu:
        raise ValueError("Le fichier est vide.")
    if len(contenu) > TAILLE_MAX_FICHIER:
        raise ValueError("Le fichier dépasse la limite de 4 Mo.")

    pages: list[PageText] = []
    if suffixe == ".pdf":
        if not contenu.startswith(b"%PDF-"):
            raise ValueError("La signature binaire du PDF est invalide.")
        try:
            reader = PdfReader(io.BytesIO(contenu), strict=True)
            if len(reader.pages) > 250:
                raise ValueError("Le PDF dépasse 250 pages.")
            segments = [(idx, page.extract_text() or "") for idx, page in enumerate(reader.pages, 1)]
            if any(not text.strip() for _, text in segments):
                segments = _ocr_blank_pages(contenu, segments)
            texte, pages = _assembler_pages(segments)
        except ValueError:
            raise
        except Exception as erreur:
            raise ValueError("Le PDF ne peut pas être lu.") from erreur
        if not texte.strip():
            raise ValueError("Aucun texte exploitable trouvé. Les PDF scannés nécessitent un OCR local configuré.")
    elif suffixe == ".docx":
        texte = _extraire_docx(contenu)
        pages = [PageText(None, 0, len(texte))]
    elif suffixe == ".eml":
        texte = _extraire_email(contenu)
        pages = [PageText(None, 0, len(texte))]
    elif suffixe == ".json":
        try:
            objet = json.loads(contenu.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ValueError("Le fichier JSON est invalide ou n'est pas encodé en UTF-8.") from erreur
        texte = _json_vers_texte(objet)
        pages = [PageText(None, 0, len(texte))]
    else:
        try:
            texte = contenu.decode("utf-8-sig")
        except UnicodeDecodeError as erreur:
            raise ValueError("Le document texte doit être encodé en UTF-8.") from erreur
        pages = [PageText(None, 0, len(texte))]

    if len(texte) > TAILLE_MAX_TEXTE:
        raise ValueError("Le texte extrait dépasse la limite de traitement.")
    if not texte.strip():
        raise ValueError("Aucun texte exploitable n'a été trouvé dans ce document.")
    return texte, MIMES[suffixe], pages, hashlib.sha256(contenu).hexdigest()


def decouper_passages(texte: str, pages: list[PageText], taille: int = 1200) -> list[dict[str, int | str | None]]:
    """Découpe sans perdre les offsets et associe les pages des PDF.

    Args:
        texte: Texte extrait complet.
        pages: Plages de texte source (page PDF ou document entier).
        taille: Taille cible en caractères.

    Returns:
        Passages avec offsets absolus dans ``texte``.
    """
    passages: list[dict[str, int | str | None]] = []
    start = 0
    while start < len(texte):
        end = min(start + taille, len(texte))
        if end < len(texte):
            boundary = texte.rfind(" ", start + taille // 2, end)
            if boundary > start:
                end = boundary
        while start < end and texte[start].isspace():
            start += 1
        while end > start and texte[end - 1].isspace():
            end -= 1
        if end > start:
            page = next((p.page for p in pages if p.page is not None and p.start < end and p.end > start), None)
            passages.append({"texte": texte[start:end], "debut": start, "fin": end, "page": page})
        start = max(end, start + 1)
    return passages


def _assembler_pages(segments: list[tuple[int, str]]) -> tuple[str, list[PageText]]:
    texte: list[str] = []
    pages: list[PageText] = []
    offset = 0
    for numero, segment in segments:
        if texte:
            texte.append("\n\n")
            offset += 2
        nettoye = segment.strip()
        pages.append(PageText(numero, offset, offset + len(nettoye)))
        texte.append(nettoye)
        offset += len(nettoye)
    return "".join(texte), pages


def _ocr_blank_pages(contenu: bytes, segments: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Tente un OCR Tesseract local sur les pages sans texte, sans réseau.

    Args:
        contenu: PDF original.
        segments: Texte natif extrait page par page.

    Returns:
        Segments avec OCR local lorsque le binaire et les langues sont disponibles.
    """
    pages_vierges = [numero for numero, texte in segments if not texte.strip()]
    if not pages_vierges:
        return segments
    if len(pages_vierges) > 30:
        return segments
    try:
        import pymupdf
        import pytesseract
        from PIL import Image
        pytesseract.get_tesseract_version()  # vérifie que le moteur est déjà installé localement
        pdf = pymupdf.open(stream=contenu, filetype="pdf")
        resultat = []
        for numero, texte in segments:
            if texte.strip():
                resultat.append((numero, texte))
                continue
            page = pdf.load_page(numero - 1)
            pixmap = page.get_pixmap(dpi=120, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            try:
                extrait = pytesseract.image_to_string(image, lang="fra+eng")
            except Exception:
                extrait = pytesseract.image_to_string(image, lang="eng")
            resultat.append((numero, extrait))
        pdf.close()
        return resultat
    except Exception:
        return segments


def _extraire_docx(contenu: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            infos = archive.infolist()
            total = sum(i.file_size for i in infos)
            if total > 25 * 1024 * 1024 or len(infos) > 300:
                raise ValueError("Le DOCX contient trop de données compressées.")
            info = archive.getinfo("word/document.xml")
            if info.file_size > 8 * 1024 * 1024:
                raise ValueError("Le contenu DOCX dépasse la limite.")
            xml = archive.read(info)
    except (zipfile.BadZipFile, KeyError, OSError) as erreur:
        raise ValueError("Le fichier DOCX n'est pas un document Word valide.") from erreur
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as erreur:
        raise ValueError("Le contenu XML DOCX est invalide.") from erreur
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join("".join(t.text or "" for t in p.findall(".//w:t", ns)) for p in root.findall(".//w:p", ns))


def _extraire_email(contenu: bytes) -> str:
    try:
        message = email.message_from_bytes(contenu, policy=policy.default)
    except Exception as erreur:
        raise ValueError("Le courriel EML est invalide.") from erreur
    parties: list[str] = []
    if message.is_multipart():
        elements = message.walk()
    else:
        elements = [message]
    for part in elements:
        if part.get_content_disposition() == "attachment":
            continue
        contenu_part = part.get_content()
        if not isinstance(contenu_part, str):
            continue
        if part.get_content_type() == "text/html":
            parser = _TexteHTML()
            parser.feed(contenu_part)
            contenu_part = html.unescape("".join(parser.parts))
        if part.get_content_type() in {"text/plain", "text/html"}:
            parties.append(contenu_part)
    headers = "\n".join(f"{nom}: {message.get(nom)}" for nom in ("Date", "From", "To", "Subject") if message.get(nom))
    return f"{headers}\n\n{'\n'.join(parties)}".strip()


def _json_vers_texte(objet: object) -> str:
    lignes: list[str] = []

    def parcourir(valeur: object, chemin: str) -> None:
        if isinstance(valeur, dict):
            for cle, element in valeur.items():
                parcourir(element, f"{chemin}.{cle}" if chemin else str(cle))
        elif isinstance(valeur, list):
            for index, element in enumerate(valeur):
                parcourir(element, f"{chemin}[{index}]")
        elif valeur is None or isinstance(valeur, (str, int, float, bool)):
            lignes.append(f"{chemin}: {valeur}")

    parcourir(objet, "")
    return "\n".join(lignes)

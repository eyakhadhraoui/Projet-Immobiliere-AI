"""Découpage du guide PDF en chunks : un chunk par fiche + deux chunks d'introduction."""
import re
from dataclasses import dataclass, field
from pypdf import PdfReader

PAGE_HEADER = re.compile(r"^Guide de diagnostic - maintenance du logement.*$", re.MULTILINE)
PAGE_NUMBER = re.compile(r"^Page \d+\s*$", re.MULTILINE)
SECTION_TITLE = re.compile(r"^Catégorie : [A-ZÉÈ]+\s*$", re.MULTILINE)
CARD_HEADER = re.compile(r"^FICHE (?P<id>[A-Z]{4}-\d{2}) \|", re.MULTILINE)
CARD_META = re.compile(
    r"FICHE (?P<id>[A-Z]{4}-\d{2}) \| Catégorie : (?P<category>\w+) \| "
    r"Pièces fréquentes : (?P<rooms>.+?) \| Urgence typique :\s*(?P<urgency>\w+)",
    re.DOTALL,
)
CARD_REF = re.compile(r"\b[A-Z]{4}-\d{2}\b")


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def clean(text: str) -> str:
    text = PAGE_HEADER.sub("", text)
    text = PAGE_NUMBER.sub("", text)
    text = SECTION_TITLE.sub("", text)
    text = re.sub(r"^-[ \t]*\n", "- ", text, flags=re.MULTILINE)  # recolle les puces
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_chunks(pdf_path: str) -> list[Chunk]:
    text = clean(extract_text(pdf_path))
    starts = [m.start() for m in CARD_HEADER.finditer(text)]
    if not starts:
        raise ValueError("Aucune fiche trouvée dans le PDF.")

    chunks: list[Chunk] = []

    # Introduction : avant la première fiche. On la sépare en deux à partir des règles de sécurité.
    intro = text[: starts[0]]
    # Le titre de la fiche est avant la ligne FICHE : on retire la dernière ligne (titre de ELEC-01)
    intro = intro.rsplit("\n", 1)[0] if "\n" in intro else intro
    split_at = intro.find("Règles générales de sécurité")
    if split_at == -1:
        raise ValueError("Section « Règles générales de sécurité » introuvable.")
    chunks.append(Chunk("INTRO-URGENCE", intro[:split_at].strip(), {"type": "intro"}))
    chunks.append(Chunk("INTRO-SECURITE", intro[split_at:].strip(), {"type": "securite"}))

    # Fiches : du titre (ligne avant FICHE) jusqu'au titre de la fiche suivante
    bounds = []
    for start in starts:
        line_start = text.rfind("\n", 0, start - 1) + 1
        bounds.append(line_start)
    bounds.append(len(text))

    for i in range(len(starts)):
        body = text[bounds[i] : bounds[i + 1]].strip()
        meta = CARD_META.search(body)
        if not meta:
            raise ValueError(f"Ligne de métadonnées illisible pour la fiche à la position {starts[i]}.")
        card_id = meta["id"]
        refs = sorted(set(CARD_REF.findall(body)) - {card_id})
        chunks.append(Chunk(
            id=card_id,
            text=body,
            metadata={
                "type": "fiche",
                "category": meta["category"],
                "rooms": " ".join(meta["rooms"].split()),
                "urgency": meta["urgency"],
                "refs": ",".join(refs),
            },
        ))
    return chunks
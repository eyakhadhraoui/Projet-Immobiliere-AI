"""Additive reliability controls and photo fingerprints for listings."""

from pathlib import Path
import hashlib

import imagehash
import sqlalchemy as sa
from alembic import op
from flask import current_app
from PIL import Image


revision = "f21c8d4a90ab"
down_revision = "d14fa93b7c20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("annonces") as batch:
        batch.add_column(sa.Column("motif_attente", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("revue_demandee_le", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("empreintes_refusees", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
    with op.batch_alter_table("annonce_photos") as batch:
        batch.add_column(sa.Column("sha256", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("phash", sa.String(length=16), nullable=True))

    op.create_table(
        "controle_fiabilite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("annonce_id", sa.Integer(), nullable=False),
        sa.Column("niveau", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("raisons", sa.JSON(), nullable=False),
        sa.Column("doublons", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("modele_texte", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("calcule_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["annonce_id"], ["annonces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("annonce_id", name="uq_controle_fiabilite_annonce"),
    )
    op.create_index("ix_controle_fiabilite_annonce_id", "controle_fiabilite", ["annonce_id"])

    # Backfill fingerprints when local originals are present. Missing/unreadable files remain NULL.
    bind = op.get_bind()
    uploads = Path(current_app.config["UPLOAD_FOLDER"])
    rows = bind.execute(sa.text("SELECT id, url FROM annonce_photos WHERE sha256 IS NULL OR phash IS NULL")).all()
    for photo_id, url in rows:
        if not isinstance(url, str) or not url.startswith("/uploads/"):
            continue
        path = uploads / Path(url).name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        perceptual = None
        try:
            with Image.open(path) as image:
                perceptual = str(imagehash.phash(image.convert("RGB")))
        except Exception:
            pass
        bind.execute(
            sa.text("UPDATE annonce_photos SET sha256=:sha, phash=:phash WHERE id=:id"),
            {"sha": sha, "phash": perceptual, "id": photo_id},
        )


def downgrade():
    op.drop_index("ix_controle_fiabilite_annonce_id", table_name="controle_fiabilite")
    op.drop_table("controle_fiabilite")
    with op.batch_alter_table("annonce_photos") as batch:
        batch.drop_column("phash")
        batch.drop_column("sha256")
    with op.batch_alter_table("annonces") as batch:
        batch.drop_column("empreintes_refusees")
        batch.drop_column("revue_demandee_le")
        batch.drop_column("motif_attente")

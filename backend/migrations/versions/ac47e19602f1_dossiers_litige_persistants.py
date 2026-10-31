"""Create private, relational rental dispute case storage.

Revision ID: ac47e19602f1
Revises: f21c8d4a90ab
"""

from alembic import op
import sqlalchemy as sa


revision = "ac47e19602f1"
down_revision = "f21c8d4a90ab"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dossiers_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("proprietaire_id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("langue", sa.String(length=5), nullable=False),
        sa.Column("juridiction", sa.String(length=120), nullable=True),
        sa.Column("provenance", sa.String(length=120), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proprietaire_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("case_id", name="uq_dossiers_litige_case_id"),
    )
    op.create_index("ix_dossiers_litige_case_id", "dossiers_litige", ["case_id"])
    op.create_index("ix_dossiers_litige_proprietaire_id", "dossiers_litige", ["proprietaire_id"])

    op.create_table(
        "documents_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("nom_fichier", sa.String(length=255), nullable=False),
        sa.Column("nom_stocke", sa.String(length=80), nullable=False),
        sa.Column("titre", sa.String(length=255), nullable=False),
        sa.Column("auteur", sa.String(length=160), nullable=True),
        sa.Column("role_auteur", sa.String(length=32), nullable=False),
        sa.Column("date_document", sa.Date(), nullable=True),
        sa.Column("texte_extrait", sa.Text(), nullable=False),
        sa.Column("hash_fichier", sa.String(length=64), nullable=False),
        sa.Column("type_mime", sa.String(length=120), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["dossiers_litige.case_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("nom_stocke", name="uq_documents_litige_nom_stocke"),
        sa.UniqueConstraint("case_id", "hash_fichier", name="uq_litige_document_hash_case"),
    )
    op.create_index("ix_documents_litige_case_id", "documents_litige", ["case_id"])

    op.create_table(
        "passages_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("texte", sa.Text(), nullable=False),
        sa.Column("debut", sa.Integer(), nullable=False),
        sa.Column("fin", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("retrieval_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["dossiers_litige.case_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents_litige.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chunk_id", name="uq_passages_litige_chunk_id"),
    )
    op.create_index("ix_passages_litige_case_id", "passages_litige", ["case_id"])
    op.create_index("ix_passages_litige_document_id", "passages_litige", ["document_id"])
    op.create_index("ix_passages_litige_chunk_id", "passages_litige", ["chunk_id"])

    op.create_table(
        "classifications_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("type_preuve", sa.String(length=40), nullable=False),
        sa.Column("sujet", sa.String(length=40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("revue_humaine", sa.Boolean(), nullable=False),
        sa.Column("verifie_manuellement", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["passages_litige.chunk_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chunk_id", name="uq_classifications_litige_chunk_id"),
    )
    op.create_index("ix_classifications_litige_chunk_id", "classifications_litige", ["chunk_id"])

    op.create_table(
        "dates_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("date_normalisee", sa.Date(), nullable=False),
        sa.Column("texte_source", sa.String(length=1000), nullable=False),
        sa.Column("attribution", sa.String(length=32), nullable=False),
        sa.Column("verifiee", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["passages_litige.chunk_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_dates_litige_chunk_id", "dates_litige", ["chunk_id"])
    op.create_index("ix_dates_litige_date_normalisee", "dates_litige", ["date_normalisee"])

    op.create_table(
        "annotations_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("auteur_id", sa.Integer(), nullable=False),
        sa.Column("etiquette", sa.String(length=80), nullable=False),
        sa.Column("valeur", sa.Text(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["passages_litige.chunk_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_annotations_litige_chunk_id", "annotations_litige", ["chunk_id"])
    op.create_index("ix_annotations_litige_auteur_id", "annotations_litige", ["auteur_id"])

    op.create_table(
        "questions_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("question", sa.String(length=1000), nullable=False),
        sa.Column("answer_status", sa.String(length=40), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["dossiers_litige.case_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_questions_litige_case_id", "questions_litige", ["case_id"])

    op.create_table(
        "citations_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions_litige.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["passages_litige.chunk_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_citations_litige_question_id", "citations_litige", ["question_id"])
    op.create_index("ix_citations_litige_chunk_id", "citations_litige", ["chunk_id"])

    op.create_table(
        "rapports_litige",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("format", sa.String(length=12), nullable=False),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["dossiers_litige.case_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("report_id", name="uq_rapports_litige_report_id"),
    )
    op.create_index("ix_rapports_litige_report_id", "rapports_litige", ["report_id"])
    op.create_index("ix_rapports_litige_case_id", "rapports_litige", ["case_id"])


def downgrade():
    op.drop_index("ix_rapports_litige_case_id", table_name="rapports_litige")
    op.drop_index("ix_rapports_litige_report_id", table_name="rapports_litige")
    op.drop_table("rapports_litige")
    op.drop_index("ix_citations_litige_chunk_id", table_name="citations_litige")
    op.drop_index("ix_citations_litige_question_id", table_name="citations_litige")
    op.drop_table("citations_litige")
    op.drop_index("ix_questions_litige_case_id", table_name="questions_litige")
    op.drop_table("questions_litige")
    op.drop_index("ix_annotations_litige_auteur_id", table_name="annotations_litige")
    op.drop_index("ix_annotations_litige_chunk_id", table_name="annotations_litige")
    op.drop_table("annotations_litige")
    op.drop_index("ix_dates_litige_date_normalisee", table_name="dates_litige")
    op.drop_index("ix_dates_litige_chunk_id", table_name="dates_litige")
    op.drop_table("dates_litige")
    op.drop_index("ix_classifications_litige_chunk_id", table_name="classifications_litige")
    op.drop_table("classifications_litige")
    op.drop_index("ix_passages_litige_chunk_id", table_name="passages_litige")
    op.drop_index("ix_passages_litige_document_id", table_name="passages_litige")
    op.drop_index("ix_passages_litige_case_id", table_name="passages_litige")
    op.drop_table("passages_litige")
    op.drop_index("ix_documents_litige_case_id", table_name="documents_litige")
    op.drop_table("documents_litige")
    op.drop_index("ix_dossiers_litige_proprietaire_id", table_name="dossiers_litige")
    op.drop_index("ix_dossiers_litige_case_id", table_name="dossiers_litige")
    op.drop_table("dossiers_litige")

"""Add risk events and one-time email challenges for login security."""

from alembic import op
import sqlalchemy as sa

revision = "b294cc67e201"
down_revision = "a83f12d6c901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evenements_connexion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=True),
        sa.Column("reussie", sa.Boolean(), nullable=False),
        sa.Column("heure_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("navigateur", sa.String(length=40), nullable=False),
        sa.Column("appareil", sa.String(length=24), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("niveau_risque", sa.String(length=16), nullable=False),
        sa.Column("score_risque", sa.Float(), nullable=False),
        sa.Column("retour_utilisateur", sa.String(length=12), nullable=True),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for nom, colonne in (("utilisateur_id", "utilisateur_id"), ("reussie", "reussie"), ("heure_utc", "heure_utc")):
        op.create_index(f"ix_evenements_connexion_{nom}", "evenements_connexion", [colonne])
    op.create_table(
        "verifications_connexion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jeton_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("evenement_id", sa.Integer(), nullable=False),
        sa.Column("expire_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nb_echecs", sa.Integer(), nullable=False),
        sa.Column("utilise_le", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["evenement_id"], ["evenements_connexion.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verifications_connexion_jeton_hash", "verifications_connexion", ["jeton_hash"], unique=True)
    op.create_index("ix_verifications_connexion_utilisateur_id", "verifications_connexion", ["utilisateur_id"])


def downgrade():
    op.drop_index("ix_verifications_connexion_utilisateur_id", table_name="verifications_connexion")
    op.drop_index("ix_verifications_connexion_jeton_hash", table_name="verifications_connexion")
    op.drop_table("verifications_connexion")
    op.drop_index("ix_evenements_connexion_heure_utc", table_name="evenements_connexion")
    op.drop_index("ix_evenements_connexion_reussie", table_name="evenements_connexion")
    op.drop_index("ix_evenements_connexion_utilisateur_id", table_name="evenements_connexion")
    op.drop_table("evenements_connexion")

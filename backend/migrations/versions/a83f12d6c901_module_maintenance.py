"""Add rental maintenance requests, events and notifications."""

from alembic import op
import sqlalchemy as sa

revision = "a83f12d6c901"
down_revision = "7be33658b3d0"
branch_labels = None
depends_on = None


def upgrade():
    categorie = sa.Enum("plomberie", "electricite", "climatisation", "serrurerie", "electromenager", "autre", name="categorie_maintenance")
    priorite = sa.Enum("basse", "normale", "haute", "urgente", name="priorite_maintenance")
    statut = sa.Enum("signalee", "acceptee", "assignee", "planifiee", "cloturee", "refusee", name="statut_maintenance")
    op.create_table(
        "demandes_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(24), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("locataire_id", sa.Integer(), nullable=False),
        sa.Column("proprietaire_id", sa.Integer(), nullable=False),
        sa.Column("categorie", categorie, nullable=False),
        sa.Column("titre", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("photos", sa.JSON(), nullable=False),
        sa.Column("priorite", priorite, nullable=False),
        sa.Column("statut", statut, nullable=False),
        sa.Column("technicien_nom", sa.String(160)),
        sa.Column("technicien_telephone", sa.String(30)),
        sa.Column("date_intervention", sa.DateTime(timezone=True)),
        sa.Column("cout_estime", sa.Numeric(12, 3)),
        sa.Column("cout_reel", sa.Numeric(12, 3)),
        sa.Column("note_cloture", sa.Text()),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_maj", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locataire_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proprietaire_id"], ["utilisateurs.id"], ondelete="CASCADE"),
    )
    for name, column in (("reference", "reference"), ("location_id", "location_id"),
                         ("locataire_id", "locataire_id"), ("proprietaire_id", "proprietaire_id"),
                         ("priorite", "priorite"), ("statut", "statut"), ("date_creation", "date_creation")):
        op.create_index(f"ix_demandes_maintenance_{name}", "demandes_maintenance", [column], unique=(name == "reference"))
    op.create_table(
        "evenements_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("demande_id", sa.Integer(), nullable=False),
        sa.Column("auteur_id", sa.Integer()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["demande_id"], ["demandes_maintenance.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_evenements_maintenance_demande_id", "evenements_maintenance", ["demande_id"])
    op.create_index("ix_evenements_maintenance_date_creation", "evenements_maintenance", ["date_creation"])
    op.create_table(
        "notifications_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("demande_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("lue", sa.Boolean(), nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["demande_id"], ["demandes_maintenance.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_maintenance_utilisateur_id", "notifications_maintenance", ["utilisateur_id"])
    op.create_index("ix_notifications_maintenance_demande_id", "notifications_maintenance", ["demande_id"])
    op.create_index("ix_notifications_maintenance_lue", "notifications_maintenance", ["lue"])
    op.create_index("ix_notifications_maintenance_date_creation", "notifications_maintenance", ["date_creation"])


def downgrade():
    op.drop_table("notifications_maintenance")
    op.drop_table("evenements_maintenance")
    op.drop_table("demandes_maintenance")

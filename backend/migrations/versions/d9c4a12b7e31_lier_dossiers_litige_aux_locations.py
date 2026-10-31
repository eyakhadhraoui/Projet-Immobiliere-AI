"""Link each dispute dossier to an optional rental contract.

Revision ID: d9c4a12b7e31
Revises: 1de8b8faa104
"""

from alembic import op
import sqlalchemy as sa


revision = "d9c4a12b7e31"
down_revision = "1de8b8faa104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the nullable location link without changing existing case records."""
    with op.batch_alter_table("dossiers_litige") as batch_op:
        batch_op.add_column(sa.Column("location_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_dossiers_litige_location_id_locations",
            "locations",
            ["location_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_dossiers_litige_location_id", ["location_id"])


def downgrade() -> None:
    """Remove the optional rental contract link."""
    with op.batch_alter_table("dossiers_litige") as batch_op:
        batch_op.drop_index("ix_dossiers_litige_location_id")
        batch_op.drop_constraint("fk_dossiers_litige_location_id_locations", type_="foreignkey")
        batch_op.drop_column("location_id")

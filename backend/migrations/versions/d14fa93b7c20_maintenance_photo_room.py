"""Add optional room information to maintenance requests."""

from alembic import op
import sqlalchemy as sa

revision = "d14fa93b7c20"
down_revision = ("c3d98f20a471", "ff28e3754b59")
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("demandes_maintenance") as batch_op:
        batch_op.add_column(sa.Column("piece", sa.String(length=32), nullable=True))


def downgrade():
    with op.batch_alter_table("demandes_maintenance") as batch_op:
        batch_op.drop_column("piece")

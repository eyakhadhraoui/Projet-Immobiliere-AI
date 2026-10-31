"""Store optional coarse GeoIP location for each login event."""

from alembic import op
import sqlalchemy as sa

revision = "c3d98f20a471"
down_revision = "b294cc67e201"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("evenements_connexion") as batch_op:
        batch_op.add_column(sa.Column("lieu_approximatif", sa.String(length=160), nullable=True))


def downgrade():
    with op.batch_alter_table("evenements_connexion") as batch_op:
        batch_op.drop_column("lieu_approximatif")

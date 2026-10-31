"""annonces rattachees aux utilisateurs

USER-002 : annonces.owner_id devient une clé étrangère vers utilisateurs.id.
Les annonces existantes (créées avec owner_id = 1 en dur) sont rattachées au propriétaire de démonstration
(id 1, créé par « flask --app run seed-utilisateurs »). Si des annonces existent sans ce compte, la migration
s'arrête avec un message explicite au lieu de créer des annonces orphelines.

Revision ID: 2152eba155d0
Revises: ff28e3754b59
Create Date: 2026-10-23 15:56:41.681057

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2152eba155d0'
down_revision = 'ff28e3754b59'
branch_labels = None
depends_on = None

ID_PROPRIETAIRE_DEMO = 1


def upgrade():
    connexion = op.get_bind()
    nb_annonces = connexion.execute(sa.text("SELECT COUNT(*) FROM annonces")).scalar()
    if nb_annonces:
        role = connexion.execute(
            sa.text("SELECT role FROM utilisateurs WHERE id = :id"), {"id": ID_PROPRIETAIRE_DEMO}
        ).scalar()
        if role != "proprietaire":
            raise RuntimeError(
                f"{nb_annonces} annonce(s) existent mais l'utilisateur {ID_PROPRIETAIRE_DEMO} n'est pas un "
                "propriétaire (ou n'existe pas). Créez d'abord le propriétaire de démonstration : "
                "flask --app run seed-utilisateurs"
            )
        connexion.execute(sa.text("UPDATE annonces SET owner_id = :id"), {"id": ID_PROPRIETAIRE_DEMO})

    with op.batch_alter_table('annonces', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_annonces_owner_id_utilisateurs', 'utilisateurs', ['owner_id'], ['id'])


def downgrade():
    # Les annonces gardent leur owner_id ; seule la contrainte est retirée.
    with op.batch_alter_table('annonces', schema=None) as batch_op:
        batch_op.drop_constraint('fk_annonces_owner_id_utilisateurs', type_='foreignkey')

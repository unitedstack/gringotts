"""add columes to account

Revision ID: 2d44a0b2cee4
Revises: 25fa0c3b7e89
Create Date: 2014-04-18 14:02:40.375941

"""

# revision identifiers, used by Alembic.
revision = '2d44a0b2cee4'
down_revision = '25fa0c3b7e89'

from alembic import op
import sqlalchemy as sa

from gringotts.services import keystone


def upgrade():
    op.add_column('account', sa.Column('level', sa.Integer))
    op.add_column('account', sa.Column('owed', sa.Boolean))
    op.add_column('order', sa.Column('owed', sa.Boolean))

    admin_project_id = keystone.get_admin_tenant_id()

    op.execute("UPDATE account set level=3, owed=0")
    op.execute("UPDATE account set level=9, owed=0 where project_id='%s'" %
               admin_project_id)
    op.execute("UPDATE `order` set owed=0")

def downgrade():
    op.drop_column('account', 'level')
    op.drop_column('account', 'owed')
    op.drop_column('order', 'owed')

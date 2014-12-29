"""add remarks to charge

Revision ID: 529a83cff1f4
Revises: 4e9e88cbddf4
Create Date: 2014-12-29 02:50:07.880143

"""

# revision identifiers, used by Alembic.
revision = '529a83cff1f4'
down_revision = '4e9e88cbddf4'

from alembic import op
import sqlalchemy as sa

from gringotts.services import keystone


def upgrade():
    op.add_column('charge', sa.Column('operator', sa.String(64)))
    op.add_column('charge', sa.Column('remarks', sa.String(255)))

    admin_user_id = keystone.get_admin_user_id()
    op.execute("UPDATE charge set operator='%s'" % admin_user_id)

def downgrade():
    op.drop_column('charge', 'operator')
    op.drop_column('charge', 'remarks')

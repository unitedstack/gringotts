"""Add sales_id to account

Revision ID: 14f673a62f43
Revises: 5e3273a5a0e
Create Date: 2015-06-11 03:46:54.963690

"""

# revision identifiers, used by Alembic.
revision = '14f673a62f43'
down_revision = '5e3273a5a0e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('sales_id', sa.String(255)))

def downgrade():
    op.drop_column('account', 'sales_id')

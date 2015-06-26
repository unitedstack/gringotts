"""Add extra column to product and subscription

Revision ID: 1713a7107ddd
Revises: 5e3273a5a0e
Create Date: 2015-06-23 19:55:52.896610

"""

# revision identifiers, used by Alembic.
revision = '1713a7107ddd'
down_revision = '5e3273a5a0e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('product', sa.Column('extra', sa.Text))
    op.add_column('subscription', sa.Column('extra', sa.Text))


def downgrade():
    op.drop_column('product', 'extra')
    op.drop_column('subscription', 'extra')

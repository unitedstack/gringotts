"""add renew to order

Revision ID: 12ac3bb16b46
Revises: 1ba1181ec5ae
Create Date: 2015-10-08 00:21:07.108817

"""

# revision identifiers, used by Alembic.
revision = '12ac3bb16b46'
down_revision = '1ba1181ec5ae'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('frozen_balance', sa.DECIMAL(20, 4)))
    op.add_column('order', sa.Column('renew', sa.Boolean))
    op.add_column('order', sa.Column('renew_method', sa.String(64)))
    op.add_column('order', sa.Column('renew_period', sa.Integer))

    op.execute("UPDATE account set frozen_balance=0")
    op.execute("UPDATE `order` set renew=0, unit='hour'")


def downgrade():
    op.drop_column('account', 'frozen_balance')
    op.drop_column('order', 'renew')
    op.drop_column('order', 'renew_method')
    op.drop_column('order', 'renew_period')

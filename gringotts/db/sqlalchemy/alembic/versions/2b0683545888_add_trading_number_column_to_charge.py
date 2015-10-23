"""add trading number column to charge

Revision ID: 2b0683545888
Revises: 12ac3bb16b46
Create Date: 2015-10-22 03:49:54.198976

"""

# revision identifiers, used by Alembic.
revision = '2b0683545888'
down_revision = '12ac3bb16b46'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('charge', sa.Column('trading_number', sa.String(255)))


def downgrade():
    op.drop_column('charge', 'trading_number')

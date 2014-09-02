"""add charged to orders

Revision ID: 10201cd7f913
Revises: 12d053556aee
Create Date: 2014-09-02 07:57:30.531958

"""

# revision identifiers, used by Alembic.
revision = '10201cd7f913'
down_revision = '12d053556aee'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('order', sa.Column('charged', sa.Boolean))
    op.execute("UPDATE `order` set charged=0")


def downgrade():
    op.drop_column('order', 'charged')

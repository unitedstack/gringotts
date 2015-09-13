"""add operator_id to precharge

Revision ID: 1ba1181ec5ae
Revises: 14f673a62f43
Create Date: 2015-09-13 02:58:49.243846

"""

# revision identifiers, used by Alembic.
revision = '1ba1181ec5ae'
down_revision = '14f673a62f43'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('precharge', sa.Column('operator_id', sa.String(255)))


def downgrade():
    op.drop_column('precharge', 'operator_id')

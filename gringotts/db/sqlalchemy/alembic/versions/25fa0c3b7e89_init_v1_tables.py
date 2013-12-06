"""init v1 tables

Revision ID: 25fa0c3b7e89
Revises: None
Create Date: 2013-12-06 12:02:35.117968

"""

# revision identifiers, used by Alembic.
revision = '25fa0c3b7e89'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'product',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('uuid', sa.String(255)),
        sa.Column('name', sa.String(255)),
        sa.Column('description', sa.String(255)),

        sa.Column('meter_name', sa.String(255)),
        sa.Column('source', sa.String(255)),

        sa.Column('region_id', sa.String(255)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),

        sa.Column('type', sa.String(255)),
        sa.Column('time_size', sa.Integer),
        sa.Column('time_unit', sa.String(255)),
        sa.Column('quantity_from', sa.Integer),
        sa.Column('quantity_to', sa.Integer),
        sa.Column('quantity_unit', sa.String(255)),

        sa.Column('price', sa.Float),
        sa.Column('currency', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )


def downgrade():
    op.drop_table('product')

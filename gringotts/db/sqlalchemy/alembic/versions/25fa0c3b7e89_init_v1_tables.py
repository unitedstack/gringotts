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

        sa.Column('product_id', sa.String(255)),
        sa.Column('name', sa.String(255)),
        sa.Column('service', sa.String(255)),
        sa.Column('region_id', sa.String(255)),
        sa.Column('description', sa.String(255)),

        sa.Column('type', sa.String(64)),
        sa.Column('period', sa.String(64)),
        sa.Column('accurate', sa.String(64)),

        sa.Column('price', sa.Float),
        sa.Column('currency', sa.String(64)),
        sa.Column('unit', sa.String(64)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )

    op.create_table(
        'subscription',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('subscription_id', sa.String(255)),
        sa.Column('resource_id', sa.String(255)),
        sa.Column('resource_name', sa.String(255)),
        sa.Column('resource_type', sa.String(255)),
        sa.Column('resource_status', sa.String(255)),


        sa.Column('product_id', sa.String(255)),
        sa.Column('current_fee', sa.Float),
        sa.Column('cron_time', sa.DateTime),
        sa.Column('status', sa.String(64)),

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )


def downgrade():
    op.drop_table('product')
    op.drop_table('subscription')

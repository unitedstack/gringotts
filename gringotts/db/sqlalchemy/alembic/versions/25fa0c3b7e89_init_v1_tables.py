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

        sa.Column('price', sa.Float),
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
        sa.Column('resource_volume', sa.Integer),


        sa.Column('product_id', sa.String(255)),
        sa.Column('current_fee', sa.Float),
        sa.Column('cron_time', sa.DateTime),
        sa.Column('status', sa.String(64)),

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )

    op.create_table(
        'bill',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('bill_id', sa.String(255)),

        sa.Column('start_time', sa.DateTime),
        sa.Column('end_time', sa.DateTime),

        sa.Column('fee', sa.Float),
        sa.Column('price', sa.Float),
        sa.Column('unit', sa.String(64)),
        sa.Column('subscription_id', sa.String(255)),

        sa.Column('remarks', sa.String(255)),

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )

    op.create_table(
        'account',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),
        sa.Column('balance', sa.Float),
        sa.Column('consumption', sa.Float),
        sa.Column('currency', sa.String(64)),
    )

    op.create_table(
        'charge',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('charge_id', sa.String(255)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),
        sa.Column('value', sa.Float),
        sa.Column('currency', sa.String(64)),
        sa.Column('charge_time', sa.DateTime)
    )

    op.create_table(
        'region',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('region_id', sa.String(255)),
        sa.Column('name', sa.String(255)),
        sa.Column('description', sa.String(255))
    )

def downgrade():
    op.drop_table('product')
    op.drop_table('subscription')
    op.drop_table('bill')
    op.drop_table('account')
    op.drop_table('charge')
    op.drop_table('region')

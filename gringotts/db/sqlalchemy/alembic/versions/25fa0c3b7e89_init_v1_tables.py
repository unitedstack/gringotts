"""init v1 tables

Revision ID: 25fa0c3b7e89
Revises: None
Create Date: 2013-12-06 12:02:35.117968

"""

# revision identifiers, used by Alembic.
revision = '25fa0c3b7e89'
down_revision = None

import datetime
from alembic import op
import sqlalchemy as sa

from gringotts.services import keystone


def upgrade():
    op.create_table(
        'product',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('product_id', sa.String(255), index=True),
        sa.Column('name', sa.String(255)),
        sa.Column('service', sa.String(255)),
        sa.Column('region_id', sa.String(255)),
        sa.Column('description', sa.String(255)),

        sa.Column('unit_price', sa.Text),
        sa.Column('deleted', sa.Boolean),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
        sa.Column('deleted_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'order',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('order_id', sa.String(255), index=True),
        sa.Column('resource_id', sa.String(255), index=True),
        sa.Column('resource_name', sa.String(255)),

        sa.Column('type', sa.String(255)),
        sa.Column('status', sa.String(64)),

        sa.Column('unit_price', sa.DECIMAL(20,4)),
        sa.Column('unit', sa.String(64)),
        sa.Column('total_price', sa.DECIMAL(20,4)),
        sa.Column('cron_time', sa.DateTime),
        sa.Column('date_time', sa.DateTime),

        sa.Column('renew', sa.Boolean),
        sa.Column('renew_method', sa.String(64)),
        sa.Column('renew_period', sa.Integer),

        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('region_id', sa.String(255)),
        sa.Column('domain_id', sa.String(255)),

        sa.Column('charged', sa.Boolean),
        sa.Column('owed', sa.Boolean),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    op.create_index('ix_order_user_id_project_id', 'order', ['user_id', 'project_id'])
    op.create_unique_constraint('uq_order_resource_id', 'order', ['resource_id'])

    op.create_table(
        'subscription',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('subscription_id', sa.String(255), index=True),
        sa.Column('type', sa.String(64)),

        sa.Column('product_id', sa.String(255), index=True),
        sa.Column('unit_price', sa.Text),

        sa.Column('order_id', sa.String(255), index=True),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('region_id', sa.String(255)),
        sa.Column('domain_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'bill',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('bill_id', sa.String(255), index=True),

        sa.Column('start_time', sa.DateTime),
        sa.Column('end_time', sa.DateTime),

        sa.Column('type', sa.String(255)),
        sa.Column('status', sa.String(64)),

        sa.Column('unit_price', sa.DECIMAL(20,4)),
        sa.Column('unit', sa.String(64)),
        sa.Column('total_price', sa.DECIMAL(20,4)),
        sa.Column('order_id', sa.String(255), index=True),
        sa.Column('resource_id', sa.String(255)),

        sa.Column('remarks', sa.String(255)),

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('region_id', sa.String(255)),
        sa.Column('domain_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_index('ix_bill_start_end_time',
                    'bill',
                    ['start_time', 'end_time'])

    op.create_table(
        'account',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('domain_id', sa.String(255)),
        sa.Column('balance', sa.DECIMAL(20,4)),
        sa.Column('frozen_balance', sa.DECIMAL(20, 4)),
        sa.Column('consumption', sa.DECIMAL(20,4)),
        sa.Column('level', sa.Integer),
        sa.Column('owed', sa.Boolean),
        sa.Column('deleted', sa.Boolean),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
        sa.Column('deleted_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'project',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('consumption', sa.DECIMAL(20,4)),

        sa.Column('domain_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'user_project',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('consumption', sa.DECIMAL(20,4)),

        sa.Column('domain_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_unique_constraint('uq_user_project_id', 'user_project', ['user_id', 'project_id'])

    op.create_table(
        'charge',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('charge_id', sa.String(255)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('domain_id', sa.String(255)),
        sa.Column('value', sa.DECIMAL(20,4)),
        sa.Column('type', sa.String(64)),
        sa.Column('come_from', sa.String(255)),
        sa.Column('charge_time', sa.DateTime),
        sa.Column('trading_number', sa.String(255)),
        sa.Column('operator', sa.String(64)),
        sa.Column('remarks', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'precharge',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('code', sa.String(64), unique=True, index=True),
        sa.Column('price', sa.DECIMAL(20, 4)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('expired_at', sa.DateTime),
        sa.Column('deleted_at', sa.DateTime),

        sa.Column('used', sa.Boolean),
        sa.Column('dispatched', sa.Boolean),
        sa.Column('deleted', sa.Boolean),

        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('operator_id', sa.String(255)),
        sa.Column('domain_id', sa.String(255)),

        sa.Column('remarks', sa.String(255)),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'deduct',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('req_id', sa.String(255), index=True, unique=True),
        sa.Column('deduct_id', sa.String(255)),
        sa.Column('type', sa.String(64)),
        sa.Column('money', sa.DECIMAL(20, 4)),
        sa.Column('remark', sa.String(255)),

        sa.Column('order_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )



def downgrade():
    op.drop_table('product')
    op.drop_table('order')
    op.drop_table('subscription')
    op.drop_table('bill')
    op.drop_table('account')
    op.drop_table('project')
    op.drop_table('user_project')
    op.drop_table('charge')
    op.drop_table('precharge')
    op.drop_table('deduct')

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
    # Check keystone service is available first
    admin_user_id = keystone.get_admin_user_id()
    admin_project_id = keystone.get_admin_tenant_id()

    op.create_table(
        'product',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('product_id', sa.String(255), index=True),
        sa.Column('name', sa.String(255)),
        sa.Column('service', sa.String(255)),
        sa.Column('region_id', sa.String(255)),
        sa.Column('description', sa.String(255)),

        sa.Column('type', sa.String(64)),
        sa.Column('deleted', sa.Boolean),

        sa.Column('unit_price', sa.DECIMAL(20, 4)),
        sa.Column('unit', sa.String(64)),
        sa.Column('quantity', sa.Integer),
        sa.Column('total_price', sa.DECIMAL(20, 4)),

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

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('region_id', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'subscription',

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('subscription_id', sa.String(255), index=True),
        sa.Column('type', sa.String(64)),

        sa.Column('product_id', sa.String(255), index=True),
        sa.Column('unit_price', sa.DECIMAL(20,4)),
        sa.Column('unit', sa.String(64)),
        sa.Column('quantity', sa.Integer),
        sa.Column('total_price', sa.DECIMAL(20,4)),

        sa.Column('order_id', sa.String(255), index=True),

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('region_id', sa.String(255)),

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
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),
        sa.Column('balance', sa.DECIMAL(20,4)),
        sa.Column('consumption', sa.DECIMAL(20,4)),
        sa.Column('currency', sa.String(64)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'charge',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('charge_id', sa.String(255)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),
        sa.Column('value', sa.DECIMAL(20,4)),
        sa.Column('type', sa.String(64)),
        sa.Column('come_from', sa.String(255)),
        sa.Column('currency', sa.String(64)),
        sa.Column('charge_time', sa.DateTime),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    op.create_table(
        'region',

        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('region_id', sa.String(255)),
        sa.Column('name', sa.String(255)),
        sa.Column('description', sa.String(255)),

        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    # Add products
    PRODUCT_SQL_PRE = "INSERT INTO product VALUES"

    PRODUCT_SQLS = [
        "(1,'98f2ce8b-8ad3-42db-b82e-dd022381d1bc','volume.size','block_storage','RegionOne','some decs','regular',0,'0.0020','hour',0,0,'2014-02-09 08:16:10',NULL,NULL)",
        "(2,'e1cd002a-bef5-4306-b60e-8e6f54b80548','snapshot.size','block_storage','RegionOne','some decs','regular',0,'0.0002','hour',0,0,'2014-02-09 08:20:06',NULL,NULL)",
        "(3,'a7ee0483-ff48-4567-84c4-932801cacfad','ip.floating','network','RegionOne','some decs','regular',0,'0.0300','hour',0,0,'2014-02-11 08:21:17',NULL,NULL)",
        "(4,'4038d1b8-e08f-4824-9f4e-f277d15c5bfe','router','network','RegionOne','some decs','regular',0,'0.0500','hour',0,0,'2014-02-11 09:02:38',NULL,NULL)",
        "(5,'0ab4bc1b-938f-4b9e-bebd-7e91dd58c85d','instance:micro-1','compute','RegionOne','some decs','regular',0,'0.0560','hour',0,0,'2014-03-18 06:42:15',NULL,NULL)",
        "(6,'9425b452-d0fb-406c-ba1b-c00bec291a02','instance:micro-2','compute','RegionOne','some decs','regular',0,'0.1110','hour',0,0,'2014-03-18 06:42:59',NULL,NULL)",
        "(7,'33969e9b-27b3-4772-acbc-a094940493f0','instance:standard-1','compute','RegionOne','some decs','regular',0,'0.2220','hour',0,0,'2014-03-18 06:43:49',NULL,NULL)",
        "(8,'2cda8174-4b1d-4988-8d0f-e94b46442bce','instance:standard-2','compute','RegionOne','some decs','regular',0,'0.4440','hour',0,0,'2014-03-18 06:44:05',NULL,NULL)",
        "(9,'bea31dc8-4140-47ee-8b48-4983f0f28a0f','instance:standard-4','compute','RegionOne','some decs','regular',0,'0.8890','hour',0,0,'2014-03-18 06:44:22',NULL,NULL)",
        "(10,'da55dddc-aa4e-4439-ba30-8bcfba36094b','instance:standard-8','compute','RegionOne','some decs','regular',0,'1.7780','hour',0,0,'2014-03-18 06:44:46',NULL,NULL)",
        "(11,'049378d6-8918-45be-b023-00fd573267ff','instance:standard-12','compute','RegionOne','some decs','regular',0,'2.6670','hour',0,0,'2014-03-18 06:45:01',NULL,NULL)",
        "(12,'b45234b1-64fd-4572-8e71-2d5ff3e62594','instance:standard-16','compute','RegionOne','some decs','regular',0,'3.5560','hour',0,0,'2014-03-18 06:48:12',NULL,NULL)",
        "(13,'e73b7486-0071-4bf7-8ea2-dca040a8dee0','instance:memory-1','compute','RegionOne','some decs','regular',0,'0.3610','hour',0,0,'2014-03-18 06:45:41',NULL,NULL)",
        "(14,'72af128b-9e82-45e6-824d-b15fcb01fbd3','instance:memory-2','compute','RegionOne','some decs','regular',0,'0.7220','hour',0,0,'2014-03-18 06:46:02',NULL,NULL)",
        "(15,'46345fe6-ab66-4f39-b6ca-b2945557e999','instance:memory-4','compute','RegionOne','some decs','regular',0,'1.4440','hour',0,0,'2014-03-18 06:46:16',NULL,NULL)",
        "(16,'732a3fe2-2837-4e46-80cd-ae6579c99121','instance:memory-8','compute','RegionOne','some decs','regular',0,'2.8890','hour',0,0,'2014-03-18 06:46:37',NULL,NULL)",
        "(17,'b45234b1-64fd-4572-8e71-2d5ff3e62595','instance:memory-12','compute','RegionOne','some decs','regular',0,'4.3330','hour',0,0,'2014-03-18 06:48:12',NULL,NULL)",
        "(18,'41579554-6b2c-4cd9-965c-0f2544d68a24','instance:compute-2','compute','RegionOne','some decs','regular',0,'0.3330','hour',0,0,'2014-03-18 06:47:19',NULL,NULL)",
        "(19,'4d2f6900-8f75-4f8d-877d-dff4dec1a57b','instance:compute-4','compute','RegionOne','some decs','regular',0,'0.6670','hour',0,0,'2014-03-18 06:47:43',NULL,NULL)",
        "(20,'cef8cb7b-b0a5-46ff-80a5-57d82e7ac611','instance:compute-8','compute','RegionOne','some decs','regular',0,'1.3330','hour',0,0,'2014-03-18 06:47:58',NULL,NULL)",
        "(21,'b45234b1-64fd-4572-8e71-2d5ff3e62593','instance:compute-12','compute','RegionOne','some decs','regular',0,'2.0000','hour',0,0,'2014-03-18 06:48:12',NULL,NULL)",
        "(22,'98f2ce8b-8ad3-42db-b82e-dd022381d1bd','sata.volume.size','block_storage','RegionOne','some decs','regular',0,'0.0006','hour',0,0,'2014-02-09 08:16:10',NULL,NULL)",
        "(23,'895a52d2-df2e-46c0-96c0-6bbb04e15502','alarm','monitor','RegionOne','some decs','regular',0,'0.0300','hour',0,0,'2014-02-11 09:02:38',NULL,NULL)",
    ]

    for PRODUCT in PRODUCT_SQLS:
        op.execute(PRODUCT_SQL_PRE + PRODUCT)

    now = datetime.datetime.utcnow()
    ACCOUNT_SQL_PRE = "INSERT INTO account VALUES"
    ACCOUNT_SQLS = [
        "(1, '%s', '%s', 10, 0, 'CNY', '%s', '%s')" % (admin_user_id, admin_project_id, now, now),
    ]

    for ACCOUNT in ACCOUNT_SQLS:
        op.execute(ACCOUNT_SQL_PRE + ACCOUNT)


def downgrade():
    op.drop_table('product')
    op.drop_table('order')
    op.drop_table('subscription')
    op.drop_table('bill')
    op.drop_table('account')
    op.drop_table('charge')
    op.drop_table('region')

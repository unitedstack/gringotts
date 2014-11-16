"""add user project table

Revision ID: 4e9e88cbddf4
Revises: 12d053556aee
Create Date: 2014-08-27 13:20:40.238751

"""

# revision identifiers, used by Alembic.
revision = '4e9e88cbddf4'
down_revision = '10201cd7f913'

from alembic import op
import sqlalchemy as sa
import datetime

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def upgrade():

    # ensure the service is avaliable
    from gringotts.services import keystone
    from gringotts.services import billing
    billing.check_avaliable()

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
    op.create_unique_constraint('uq_order_resource_id', 'order', ['resource_id'])

    op.add_column('account', sa.Column('domain_id', sa.String(255)))
    op.add_column('order', sa.Column('domain_id', sa.String(255)))
    op.add_column('subscription', sa.Column('domain_id', sa.String(255)))
    op.add_column('bill', sa.Column('domain_id', sa.String(255)))
    op.add_column('charge', sa.Column('domain_id', sa.String(255)))
    op.add_column('precharge', sa.Column('domain_id', sa.String(255)))

    op.create_index('ix_order_user_id_project_id', 'order', ['user_id', 'project_id'])

    accounts = billing.get_accounts()
    for account in accounts:
        try:
            project = keystone.get_project(account['project_id'])
            now = datetime.datetime.utcnow().strftime(TIMESTAMP_TIME_FORMAT)
            op.execute("INSERT INTO project VALUES(0, '%s', '%s', '%s', '%s', '%s', '%s')" % \
                       (account['user_id'], account['project_id'], account['consumption'],
                        project.domain_id, account['created_at'], now))
            op.execute("INSERT INTO user_project VALUES(0, '%s', '%s', '%s', '%s', '%s', '%s')" % \
                       (account['user_id'], account['project_id'], account['consumption'],
                        project.domain_id, account['created_at'], now))
            op.execute("UPDATE account set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
            op.execute("UPDATE `order` set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
            op.execute("UPDATE `order` set user_id='%s' where project_id='%s' and user_id is NULL" % \
                       (account['user_id'], account['project_id']))
            op.execute("UPDATE subscription set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
            op.execute("UPDATE bill set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
            op.execute("UPDATE charge set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
            op.execute("UPDATE precharge set domain_id='%s' where project_id='%s'" % \
                       (project.domain_id, account['project_id']))
        except Exception as e:
            pass


def downgrade():
    pass

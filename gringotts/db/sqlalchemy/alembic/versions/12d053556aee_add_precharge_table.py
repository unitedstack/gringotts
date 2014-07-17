"""add precharge table

Revision ID: 12d053556aee
Revises: 2d44a0b2cee4
Create Date: 2014-07-17 14:27:44.978355

"""

# revision identifiers, used by Alembic.
revision = '12d053556aee'
down_revision = '2d44a0b2cee4'

from alembic import op
import sqlalchemy as sa


def upgrade():
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

        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255), index=True),

        sa.Column('remarks', sa.String(255)),

        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )


def downgrade():
    op.drop_table('precharge')

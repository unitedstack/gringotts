"""add deduct table

Revision ID: 5e3273a5a0e
Revises: 529a83cff1f4
Create Date: 2015-01-13 03:45:37.280846

"""

# revision identifiers, used by Alembic.
revision = '5e3273a5a0e'
down_revision = '49e22e86388e'

from alembic import op
import sqlalchemy as sa


def upgrade():
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
    op.drop_table('deduct')

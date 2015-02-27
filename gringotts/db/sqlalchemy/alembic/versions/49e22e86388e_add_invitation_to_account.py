"""add invitation to account

Revision ID: 49e22e86388e
Revises: 529a83cff1f4
Create Date: 2015-02-27 10:23:13.408966

"""

# revision identifiers, used by Alembic.
revision = '49e22e86388e'
down_revision = '529a83cff1f4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('inviter', sa.String(64)))
    op.add_column('account', sa.Column('charged', sa.Boolean))
    op.add_column('account', sa.Column('reward_value', sa.DECIMAL(20, 4)))

    op.create_index('ix_account_inviter', 'account', ['inviter'])

def downgrade():
    op.drop_column('account', 'inviter')
    op.drop_column('account', 'charged')
    op.drop_column('account', 'reward_value')

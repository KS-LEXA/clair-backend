"""add_deleted_contracts

Revision ID: c5a1b2d3e4f6
Revises: 71d7f2a38428
Create Date: 2026-06-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5a1b2d3e4f6'
down_revision: Union[str, None] = '71d7f2a38428'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deleted_contracts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('original_contract_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('contract_type', sa.String(length=50), nullable=True),
        sa.Column('status_at_deletion', sa.String(length=50), nullable=True),
        sa.Column('contract_created_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deleted_contracts_user_id', 'deleted_contracts', ['user_id'])
    op.create_index('ix_deleted_contracts_original_contract_id', 'deleted_contracts', ['original_contract_id'])
    op.create_index('ix_deleted_contracts_deleted_at', 'deleted_contracts', ['deleted_at'])


def downgrade() -> None:
    op.drop_index('ix_deleted_contracts_deleted_at', table_name='deleted_contracts')
    op.drop_index('ix_deleted_contracts_original_contract_id', table_name='deleted_contracts')
    op.drop_index('ix_deleted_contracts_user_id', table_name='deleted_contracts')
    op.drop_table('deleted_contracts')

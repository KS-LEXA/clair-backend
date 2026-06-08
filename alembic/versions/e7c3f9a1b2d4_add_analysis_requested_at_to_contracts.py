"""add_analysis_requested_at_to_contracts

Revision ID: e7c3f9a1b2d4
Revises: c5a1b2d3e4f6
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c3f9a1b2d4'
down_revision: Union[str, None] = 'c5a1b2d3e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 분석(재분석 포함) 요청 시각 — 재분석 신선도 판별의 기준 시각.
    op.add_column(
        'contracts',
        sa.Column('analysis_requested_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('contracts', 'analysis_requested_at')

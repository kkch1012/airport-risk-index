"""add confidence flags (has_data, is_proxy) to category_score_records

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17 10:00:00.000000

크롤링+공개데이터 전환: 카테고리 점수에 데이터 신뢰도 플래그를 영속화한다.
- has_data=False : 유효 데이터 없음(종합점수 가중치에서 제외)
- is_proxy=True  : 뉴스 신호 기반 추정치(실측 통계 아님)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'category_score_records',
        sa.Column('has_data', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    )
    op.add_column(
        'category_score_records',
        sa.Column('is_proxy', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )


def downgrade() -> None:
    op.drop_column('category_score_records', 'is_proxy')
    op.drop_column('category_score_records', 'has_data')

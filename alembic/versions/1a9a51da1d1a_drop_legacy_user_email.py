"""drop legacy plaintext users.email (email encryption step 2)

Revision ID: 1a9a51da1d1a
Revises: 3583058d4b4f
Create Date: 2026-10-21 18:00:00

이메일 컬럼 암호화 2단계 (이슈 #158).
- 1단계(3583058d4b4f)에서 이메일을 email_enc(잠근 값)·email_hash(찾기용 지문)로 옮기고 옛 평문 칸 users.email은 비워 두었다.
- 서버에서 회원 전원이 풀리고 지문이 맞는 것, 머지 전 백업과 이메일이 같은 것을 확인했으므로(10/21) 빈 칸을 지운다.
- 혹시 평문이 남아 있으면 지우지 않고 멈춘다.
- 되돌리기(downgrade)는 빈 칸(비어 있어도 되는 고유 칸)을 다시 만든다. 값은 1단계 되돌리기가 풀어서 채운다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '1a9a51da1d1a'
down_revision: Union[str, Sequence[str], None] = '3583058d4b4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    left = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM users WHERE email IS NOT NULL")).scalar_one()
    if left:
        raise RuntimeError(f"옛 평문 이메일이 {left}개 남아 있어 칸을 지우지 않고 멈춥니다. 1단계 마이그레이션을 확인하세요.")
    op.drop_column('users', 'email')   # 이 칸에 걸린 고유 인덱스도 같이 지워진다


def downgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.create_unique_constraint('email', 'users', ['email'])

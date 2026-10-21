"""encrypt user email (email_enc + email_hash)

Revision ID: 3583058d4b4f
Revises: 10af07296be1
Create Date: 2026-10-20 22:00:00

이메일 컬럼 암호화 1단계 (이슈 #144).
- 새 칸 email_enc(잠근 이메일), email_hash(찾기용 지문)를 만들고, 기존 회원의 이메일을 정리(앞뒤 공백·소문자)해 채운다.
- 옛 평문 칸 users.email은 비어 있어도 되게 바꾸고, 채운 뒤 값을 비운다. 칸 자체는 확인이 끝나면 2단계 마이그레이션에서 지운다.
- 키(PII_ENC_KEY, PII_HASH_KEY)가 .env에 없으면 아무것도 바꾸기 전에 멈춘다.
- 되돌리기(downgrade)는 잠근 이메일을 풀어 옛 칸에 되돌린 뒤 새 칸을 지운다(같은 키가 있어야 함).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core import pii

revision: str = '3583058d4b4f'
down_revision: Union[str, Sequence[str], None] = '10af07296be1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pii.require_keys()   # 키가 없으면 칸을 만들기 전에 멈춘다(반쯤 바뀐 상태가 남지 않게)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT user_id, email FROM users")).fetchall()
    hashes = [pii.email_hash(email) for _, email in rows]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("정리(소문자·앞뒤 공백) 뒤 같은 이메일이 된 회원이 있어 멈춥니다. 먼저 중복을 정리하세요.")

    op.add_column('users', sa.Column('email_enc', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('email_hash', sa.CHAR(length=64), nullable=True))
    for (user_id, email), h in zip(rows, hashes):
        conn.execute(
            sa.text("UPDATE users SET email_enc = :enc, email_hash = :h WHERE user_id = :uid"),
            {"enc": pii.encrypt(pii.normalize_email(email)), "h": h, "uid": user_id},
        )
    op.alter_column('users', 'email_enc', existing_type=sa.Text(), nullable=False)
    op.alter_column('users', 'email_hash', existing_type=sa.CHAR(length=64), nullable=False)
    op.create_index('uq_users_email_hash', 'users', ['email_hash'], unique=True)

    # 옛 평문 칸: 비울 수 있게 바꾸고 값을 지운다(칸은 2단계에서 삭제)
    op.alter_column('users', 'email', existing_type=sa.String(length=255), nullable=True)
    conn.execute(sa.text("UPDATE users SET email = NULL"))


def downgrade() -> None:
    pii.require_keys()
    conn = op.get_bind()
    for user_id, enc in conn.execute(sa.text("SELECT user_id, email_enc FROM users")).fetchall():
        conn.execute(sa.text("UPDATE users SET email = :e WHERE user_id = :uid"),
                     {"e": pii.decrypt(enc), "uid": user_id})
    op.alter_column('users', 'email', existing_type=sa.String(length=255), nullable=False)
    op.drop_index('uq_users_email_hash', table_name='users')
    op.drop_column('users', 'email_hash')
    op.drop_column('users', 'email_enc')

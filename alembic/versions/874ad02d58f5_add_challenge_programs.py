"""add challenge programs

Revision ID: 874ad02d58f5
Revises: cf92c31e0691
Create Date: 2026-10-26 13:25:56.429584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '874ad02d58f5'
down_revision: Union[str, Sequence[str], None] = 'cf92c31e0691'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenge_programs",
        sa.Column("program_id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("program_number", sa.Integer(), nullable=False),
        sa.Column("model_a_version", sa.String(length=20), nullable=True),
        sa.Column("model_b_version", sa.String(length=20), nullable=True),
        sa.Column("model_updated_on", sa.Date(), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("program_id"),
        sa.UniqueConstraint("user_id", "program_number", name="uq_challenge_program_user_number"),
    )
    op.create_index(
        op.f("ix_challenge_programs_user_id"),
        "challenge_programs",
        ["user_id"],
        unique=False,
    )

    # 기존 사이클에 먼저 비어 있는 program_id 칼럼을 추가한다.
    op.add_column(
        "challenge_cycles",
        sa.Column("program_id", sa.CHAR(length=36), nullable=True),
    )

    # 기존 사이클이 있는 사용자는 모두 기존 프로그램 1로 보존한다.
    op.execute("""
        INSERT INTO challenge_programs (
            program_id, user_id, program_number,
            model_a_version, model_b_version,
            model_updated_on, change_note,
            created_at, updated_at
        )
        SELECT
            UUID(), user_id, 1,
            NULL, NULL,
            NULL, NULL,
            MIN(created_at), MAX(updated_at)
        FROM challenge_cycles
        GROUP BY user_id
    """)
    op.execute("""
        UPDATE challenge_cycles AS cycle
        JOIN challenge_programs AS program
          ON program.user_id = cycle.user_id
         AND program.program_number = 1
        SET cycle.program_id = program.program_id
    """)

    # 기존 행까지 연결된 다음에만 필수값·외래 키로 강화한다.
    op.alter_column(
        "challenge_cycles",
        "program_id",
        existing_type=sa.CHAR(length=36),
        nullable=False,
    )
    op.create_index(
        op.f("ix_challenge_cycles_program_id"),
        "challenge_cycles",
        ["program_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_challenge_cycles_program_id",
        "challenge_cycles",
        "challenge_programs",
        ["program_id"],
        ["program_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_challenge_cycles_program_id",
        "challenge_cycles",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_challenge_cycles_program_id"),
        table_name="challenge_cycles",
    )
    op.drop_column("challenge_cycles", "program_id")
    op.drop_index(
        op.f("ix_challenge_programs_user_id"),
        table_name="challenge_programs",
    )
    op.drop_table("challenge_programs")
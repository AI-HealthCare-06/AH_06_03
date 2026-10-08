"""create challenge tables + seed catalog (카테고리 7 · 미션 10)

Revision ID: 3d0c145a545a
Revises: f1d3b7a9c2e4
Create Date: 2026-10-08 18:00:00.000000

기준: modeling/handoff/생활습관_입력_가이드.md §3.1·§4, ERD v8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3d0c145a545a'
down_revision: Union[str, Sequence[str], None] = 'f1d3b7a9c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (코드, 이름, 순서)
CATEGORIES = [
    ("SMOKING", "금연", 1), ("ALCOHOL", "절주", 2), ("SODIUM", "나트륨 줄이기", 3), ("ACTIVITY", "신체 활동", 4),
    ("EATOUT", "외식·배달 조절", 5), ("BREAKFAST", "아침 식사", 6), ("WEIGHT", "체중 관리", 7),
]
# (코드, 카테고리, 이름, 설명, 역할, 난이도, 주간 목표, target_config)
MISSIONS = [
    ("SMK-1", "SMOKING", "금연 유지 (일반담배·전자담배 모두)",
     "4주 동안 일반담배를 피우지 않아요 (전자담배로 바꾸지 않아요)", "fixed", "high", 7, None),
    ("ALC-1", "ALCOHOL", "절주: 마신 날도 남 2잔 · 여 1잔 이하",
     "술을 마신 날에도 남성 2잔, 여성 1잔까지만 마셔요", "fixed", "medium", 7, {"male_max": 2, "female_max": 1}),
    ("NA-1", "SODIUM", "국물 남기기", "국·찌개·탕·라면의 국물을 남겨요", "selectable", "low", 5, None),
    ("NA-2", "SODIUM", "음식에 소금·간장 더 넣지 않기", "식탁에서 소금이나 간장을 더 넣지 않아요", "selectable", "medium", 5, None),
    ("ACT-1", "ACTIVITY", "하루 걸음 수: 평소 + 2,000보", "하루 걸음 수를 평소보다 2,000보 늘려요", "selectable", "low", 5, None),
    ("ACT-2", "ACTIVITY", "빠르게 걷기 30분", "숨이 조금 찰 정도로 30분 이상 빠르게 걸어요",
     "selectable", "medium", 5, {"min_minutes": 30}),
    ("ACT-3", "ACTIVITY", "벽 스쿼트 (2분 버티기 × 4번)",
     "벽에 등을 대고 무릎을 굽힌 자세로 2분 버티기를 4번 해요 (사이 2분 휴식)",
     "selectable", "high", 3, {"sets": 4, "seconds_per_set": 120}),
    ("OUT-1", "EATOUT", '외식·배달 때 "싱겁게" 요청하기', '외식·배달 주문 때 "싱겁게 해 주세요"라고 요청해요',
     "selectable", "medium", 3, None),
    ("BRK-1", "BREAKFAST", "아침 식사 하기", "아침 식사를 해요", "selectable", "low", 5, None),
    ("WT-1", "WEIGHT", "끼니마다 밥 2/3공기", "끼니마다 밥을 2/3공기만 먹어요. 4주마다 몸무게·허리둘레를 다시 재요",
     "selectable", "medium", 5, None),
]


def _cat_id(n: int) -> str:
    return f"01a0f900-0000-7000-8010-{n:012d}"


def _mission_id(n: int) -> str:
    return f"01a0f900-0000-7000-8011-{n:012d}"


def _level_id(n: int) -> str:
    return f"01a0f900-0000-7000-8012-{n:012d}"


def upgrade() -> None:
    op.create_table('challenge_categories',
    sa.Column('category_id', sa.CHAR(length=36), nullable=False),
    sa.Column('category_code', sa.String(length=50), nullable=False),
    sa.Column('category_name', sa.String(length=100), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('category_id'),
    sa.UniqueConstraint('category_code')
    )
    op.create_table('challenges',
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('category_id', sa.CHAR(length=36), nullable=False),
    sa.Column('challenge_code', sa.String(length=50), nullable=False),
    sa.Column('challenge_name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('mission_role', sa.Enum('fixed', 'selectable', 'replacement', name='mission_role_type'), nullable=False),
    sa.Column('proof_type', sa.Enum('photo', 'self_record', 'automatic', 'measurement', name='proof_type'), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['challenge_categories.category_id']),
    sa.PrimaryKeyConstraint('challenge_id'),
    sa.UniqueConstraint('challenge_code')
    )
    op.create_table('challenge_levels',
    sa.Column('challenge_level_id', sa.CHAR(length=36), nullable=False),
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('difficulty', sa.Enum('low', 'medium', 'high', name='difficulty_level'), nullable=False),
    sa.Column('weekly_target', sa.Integer(), nullable=False),
    sa.Column('target_config', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['challenge_id'], ['challenges.challenge_id']),
    sa.PrimaryKeyConstraint('challenge_level_id'),
    sa.UniqueConstraint('challenge_id', 'difficulty')
    )
    op.create_table('challenge_cycles',
    sa.Column('cycle_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('cycle_number', sa.Integer(), nullable=False),
    sa.Column('started_on', sa.Date(), nullable=False),
    sa.Column('ended_on', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('active', 'completed', 'incomplete', 'stopped', name='cycle_status'), nullable=False),
    sa.Column('stopped_reason_code', sa.String(length=30), nullable=True),
    sa.Column('stopped_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('cycle_id')
    )
    op.create_index(op.f('ix_challenge_cycles_user_id'), 'challenge_cycles', ['user_id'], unique=False)
    op.create_table('cycle_challenges',
    sa.Column('cycle_challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('cycle_id', sa.CHAR(length=36), nullable=False),
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('selection_type', sa.Enum('fixed', 'replacement', 'selected', name='selection_type'), nullable=False),
    sa.Column('difficulty', sa.Enum('low', 'medium', 'high', name='difficulty_level'), nullable=False),
    sa.Column('weekly_target', sa.Integer(), nullable=False),
    sa.Column('target_config', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('active', 'completed', 'incomplete', 'stopped', name='cycle_challenge_status'), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['challenges.challenge_id']),
    sa.ForeignKeyConstraint(['cycle_id'], ['challenge_cycles.cycle_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('cycle_challenge_id'),
    sa.UniqueConstraint('cycle_id', 'challenge_id')
    )
    op.create_index(op.f('ix_cycle_challenges_cycle_id'), 'cycle_challenges', ['cycle_id'], unique=False)
    op.create_table('challenge_logs',
    sa.Column('challenge_log_id', sa.CHAR(length=36), nullable=False),
    sa.Column('cycle_challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('log_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('completed', 'failed', 'skipped', name='challenge_log_status'), nullable=False),
    sa.Column('answer', sa.String(length=30), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=8, scale=2, asdecimal=False), nullable=True),
    sa.Column('limit_exceeded', sa.Boolean(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['cycle_challenge_id'], ['cycle_challenges.cycle_challenge_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('challenge_log_id'),
    sa.UniqueConstraint('cycle_challenge_id', 'log_date')
    )
    op.create_table('user_classifications',
    sa.Column('user_classification_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('cycle_id', sa.CHAR(length=36), nullable=False),
    sa.Column('survey_instance_id', sa.CHAR(length=36), nullable=True),
    sa.Column('health_record_id', sa.CHAR(length=36), nullable=True),
    sa.Column('classification_code', sa.String(length=50), nullable=False),
    sa.Column('classification_value', sa.JSON(), nullable=False),
    sa.Column('classified_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['cycle_id'], ['challenge_cycles.cycle_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['health_record_id'], ['health_records.health_record_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['survey_instance_id'], ['survey_instances.survey_instance_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_classification_id'),
    sa.UniqueConstraint('cycle_id', 'classification_code')
    )
    op.create_index(op.f('ix_user_classifications_user_id'), 'user_classifications', ['user_id'], unique=False)

    # ---- 시드: 카테고리 7 · 미션 10 · 미션별 난이도 1행
    categories = sa.table("challenge_categories",
        sa.column("category_id", sa.CHAR(36)), sa.column("category_code", sa.String),
        sa.column("category_name", sa.String), sa.column("display_order", sa.Integer),
        sa.column("active", sa.Boolean))
    challenges = sa.table("challenges",
        sa.column("challenge_id", sa.CHAR(36)), sa.column("category_id", sa.CHAR(36)),
        sa.column("challenge_code", sa.String), sa.column("challenge_name", sa.String),
        sa.column("description", sa.Text), sa.column("mission_role", sa.String),
        sa.column("proof_type", sa.String), sa.column("active", sa.Boolean))
    levels = sa.table("challenge_levels",
        sa.column("challenge_level_id", sa.CHAR(36)), sa.column("challenge_id", sa.CHAR(36)),
        sa.column("difficulty", sa.String), sa.column("weekly_target", sa.Integer),
        sa.column("target_config", sa.JSON))

    cat_ids = {code: _cat_id(n) for n, (code, _, _) in enumerate(CATEGORIES, start=1)}
    op.bulk_insert(categories, [
        {"category_id": cat_ids[code], "category_code": code, "category_name": name,
         "display_order": order, "active": True}
        for code, name, order in CATEGORIES
    ])
    op.bulk_insert(challenges, [
        {"challenge_id": _mission_id(n), "category_id": cat_ids[cat], "challenge_code": code,
         "challenge_name": name, "description": desc, "mission_role": role,
         "proof_type": "self_record", "active": True}
        for n, (code, cat, name, desc, role, _, _, _) in enumerate(MISSIONS, start=1)
    ])
    op.bulk_insert(levels, [
        {"challenge_level_id": _level_id(n), "challenge_id": _mission_id(n), "difficulty": diff,
         "weekly_target": target, "target_config": cfg}
        for n, (_, _, _, _, _, diff, target, cfg) in enumerate(MISSIONS, start=1)
    ])


def downgrade() -> None:
    # 인덱스는 테이블과 함께 지워진다 (MySQL은 FK가 쓰는 인덱스를 따로 못 지움)
    op.drop_table('user_classifications')
    op.drop_table('challenge_logs')
    op.drop_table('cycle_challenges')
    op.drop_table('challenge_cycles')
    op.drop_table('challenge_levels')
    op.drop_table('challenges')
    op.drop_table('challenge_categories')

"""관리자 화면용 가짜 데이터 (예시. 이메일·닉네임은 모두 가짜)."""
ME = {"user_id": "u-admin", "email": "admin@paeon.example"}
CATALOG = [
    {"category_id": "c1", "category_code": "ACT", "category_name": "운동", "active": True, "switchable": True, "missions": [
        {"challenge_id": "m1", "challenge_code": "ACT-1", "challenge_name": "계단 오르기", "active": True, "switchable": True},
        {"challenge_id": "m2", "challenge_code": "ACT-2", "challenge_name": "빠르게 걷기 30분", "active": True, "switchable": True}]},
    {"category_id": "c2", "category_code": "DIET", "category_name": "식단", "active": True, "switchable": True, "missions": [
        {"challenge_id": "m3", "challenge_code": "DIET-1", "challenge_name": "국물 반만 먹기", "active": True, "switchable": True},
        {"challenge_id": "m4", "challenge_code": "DIET-2", "challenge_name": "아침 식사 챙기기", "active": False, "switchable": True}]},
    {"category_id": "c3", "category_code": "SMK", "category_name": "금연", "active": True, "switchable": False, "missions": [
        {"challenge_id": "m5", "challenge_code": "SMK-1", "challenge_name": "금연(전자담배 포함)", "active": True, "switchable": False}]},
]
USERS = {"total": 3, "items": [
    {"user_id": "u1", "user_id_short": "a1b2c3", "email_masked": "a***@gmail.com", "joined_at": "2026-10-23T01:00:00", "stage": "challenge", "health_consent": "agreed"},
    {"user_id": "u2", "user_id_short": "d4e5f6", "email_masked": "b***@naver.com", "joined_at": "2026-10-22T01:00:00", "stage": "prediction", "health_consent": "withdrawn"},
    {"user_id": "u3", "user_id_short": "g7h8i9", "email_masked": "c***@test.com", "joined_at": "2026-10-22T01:00:00", "stage": "signup", "health_consent": "none"}]}
STATS = {"cycles": {"total": 8, "users_started": 7, "active": 5, "completed": 2, "incomplete": 1, "stopped": 0, "completion_rate": 0.667, "giving_up_rate": 0.0},
         "missions": [
    {"challenge_name": "빠르게 걷기 30분", "challenge_code": "ACT-2", "selected_count": 4, "assigned_count": 4, "active_count": 3, "completed_count": 1, "incomplete_count": 0, "stopped_count": 0, "completion_rate": 1.0, "giving_up_rate": 0.0, "avg_logged_days": 12.5, "avg_completed_days": 20},
    {"challenge_name": "국물 반만 먹기", "challenge_code": "DIET-1", "selected_count": 3, "assigned_count": 3, "active_count": 2, "completed_count": 1, "incomplete_count": 1, "stopped_count": 0, "completion_rate": 0.5, "giving_up_rate": 0.0, "avg_logged_days": 9, "avg_completed_days": 18}]}
AUDIT = [
    {"created_at": "2026-10-25T05:02:00", "actor_email": "admin@paeon.example", "action": "user_detail_view", "target": "a1b2c3", "detail": None},
    {"created_at": "2026-10-25T04:40:00", "actor_email": "admin@paeon.example", "action": "inquiry_answer", "target": "i1", "detail": None},
    {"created_at": "2026-10-25T04:10:00", "actor_email": "admin@paeon.example", "action": "notice_create", "target": "n1", "detail": "새 기능 안내"}]
INQ = {"total": 2, "items": [
    {"inquiry_id": "i1", "title": "알림이 안 와요", "answered": True, "created_at": "2026-10-24T01:00:00", "user_id_short": "a1b2c3"},
    {"inquiry_id": "i2", "title": "닉네임을 바꾸고 싶어요", "answered": False, "created_at": "2026-10-22T01:00:00", "user_id_short": "d4e5f6"}]}
GUEST = {"total": 1, "items": [{"inquiry_id": "g1", "title": "로그인이 안 돼요", "answered": False, "created_at": "2026-10-24T03:00:00"}]}
NOTICES = [
    {"notice_id": "n1", "title": "새로운 기능이 추가됐어요", "body": "알림·프로필·눈 색·댓글 좋아요가 생겼어요.", "status": "active", "starts_at": "2026-10-24T01:00:00", "ends_at": None, "created_by": "admin"},
    {"notice_id": "n2", "title": "알림 받는 방법", "body": "아이폰은 홈 화면에 추가해야 알림을 받을 수 있어요.", "status": "active", "starts_at": "2026-10-23T01:00:00", "ends_at": None, "created_by": "admin"}]
REPORTS = {"total": 1, "items": [
    {"target_type": "post", "target_id": "p9", "title": "광고예요", "preview": "이 링크에서 사면 싸요", "author_nickname": "광고봇", "author_user_id": None, "report_count": 3, "reasons": {"ad": 3}, "auto_hidden": True, "last_reported_at": "2026-10-25T02:00:00", "action": None}]}
POSTS = {"total": 3, "items": [
    {"post_id": "p1", "title": "인증합니다", "preview": "오늘 술 안 마셨어요", "author_nickname": "동구리", "author_user_id": None, "status": "visible", "pending_reports": 0, "created_at": "2026-10-25T01:00:00"},
    {"post_id": "p2", "title": "국물 반만 먹기", "preview": "건더기 먼저 먹었어요", "author_nickname": "몽글이", "author_user_id": None, "status": "visible", "pending_reports": 0, "created_at": "2026-10-24T20:00:00"},
    {"post_id": "p9", "title": "광고예요", "preview": "이 링크에서 사면 싸요", "author_nickname": "광고봇", "author_user_id": None, "status": "hidden", "pending_reports": 1, "created_at": "2026-10-24T09:00:00"}]}


def cc(i, t, p, s, e, st, n, fin=None):
    return {"challenge_id": i, "title": t, "proof_type": p, "state": st, "starts_on": s, "ends_on": e, "target_steps": 7000, "participants": n,
            "rewards": {"first": 300, "second": 200, "third": 100, "complete": 20}, "complete_min_days": 5, "finalized_at": fin}


CC = {"items": [cc("cc1", "하루 7천 보", "steps", "2026-10-20", "2026-10-26", "active", 12),
                cc("cc2", "물 마시기", "self", "2026-10-27", "2026-11-02", "upcoming", 3),
                cc("cc3", "계단 오르기", "self", "2026-10-10", "2026-10-16", "ended", 8)]}

OVERVIEW = {
    "funnel": [{"label": "가입", "users": 24, "rate_of_previous": None}, {"label": "건강정보 입력", "users": 18, "rate_of_previous": 0.75},
               {"label": "분석 완료", "users": 16, "rate_of_previous": 0.89}, {"label": "챌린지 시작", "users": 12, "rate_of_previous": 0.75}],
    "activity": [{"date": f"2026-10-{d}", "signups": s, "logins": l, "active_users": a, "returning_users": r}
                 for d, s, l, a, r in [(20, 3, 9, 6, 2), (21, 5, 14, 9, 4), (22, 8, 20, 13, 6), (23, 6, 18, 12, 7), (24, 2, 15, 10, 8)]],
    "consents": [{"policy_type": "terms_of_service", "version": "v4", "agreed": 24, "withdrawn": 0},
                 {"policy_type": "privacy", "version": "v4", "agreed": 24, "withdrawn": 0},
                 {"policy_type": "health_data", "version": "v4", "agreed": 21, "withdrawn": 1}],
    "deletions": {"deleted_accounts": 2, "consent_withdrawals": 1, "recent": [{"completed_at": "2026-10-24T05:00:00", "deleted_rows": 48}]},
    "status": {"server_started_at": "2026-10-24T01:00:00", "uptime_seconds": 90000, "db_ok": True, "db_revision": "f2c9d5e83b61", "admin_count": 2},
}
JOURNEY = {"signup_from": "2026-10-22", "signup_to": "2026-10-25", "exclude_admins": True, "cohort": 26, "admins_excluded": 4,
           "stages": [
               {"code": "signup", "label": "가입", "users": 26, "from_previous": None, "skipped_previous": None, "lost": None, "biggest_loss": False},
               {"code": "eligibility", "label": "대상 확인", "users": 25, "from_previous": 25, "skipped_previous": 0, "lost": 1, "biggest_loss": False},
               {"code": "health", "label": "건강정보 입력", "users": 22, "from_previous": 21, "skipped_previous": 1, "lost": 4, "biggest_loss": True},
               {"code": "survey", "label": "설문 제출", "users": 21, "from_previous": 21, "skipped_previous": 0, "lost": 1, "biggest_loss": False},
               {"code": "prediction", "label": "분석 결과", "users": 20, "from_previous": 20, "skipped_previous": 0, "lost": 1, "biggest_loss": False},
               {"code": "challenge", "label": "챌린지 시작", "users": 19, "from_previous": 19, "skipped_previous": 0, "lost": 1, "biggest_loss": False},
               {"code": "next", "label": "다음 4주 시작", "users": 4, "from_previous": 4, "skipped_previous": 0, "lost": 15, "biggest_loss": False}],
           "record_days": [{"bucket": "0일", "users": 6, "finished_4w": 1, "started_next": 0}, {"bucket": "1일", "users": 3, "finished_4w": 1, "started_next": 0},
                           {"bucket": "2일", "users": 2, "finished_4w": 0, "started_next": 0}, {"bucket": "3일 이상", "users": 8, "finished_4w": 7, "started_next": 4}],
           "challenge_without_prediction": [{"user_id_short": "bcb65673", "signed_up_kst": "10/23 14:02"}]}
BADGES = {"total": 8, "earned_count": 4, "next": {"label": "7일 연속", "hint": "7일 연속 미션을 모두 마쳐요"}, "badges": [
    {"code": "first", "label": "첫 인증", "group": "streak", "earned": True, "progress": 1, "target": 1, "hint": "처음 인증해요"},
    {"code": "streak_3", "label": "3일 연속", "group": "streak", "earned": True, "progress": 3, "target": 3, "hint": "3일 연속"},
    {"code": "streak_7", "label": "7일 연속", "group": "streak", "earned": False, "progress": 5, "target": 7, "hint": "7일 연속 미션을 모두 마쳐요"},
    {"code": "week_1", "label": "1주 완주", "group": "streak", "earned": True, "progress": 7, "target": 7, "hint": "1주"},
    {"code": "exercise_10", "label": "운동 10회", "group": "record", "earned": True, "progress": 10, "target": 10, "hint": "운동 10회"},
    {"code": "bp_4", "label": "혈압 4번 기록", "group": "record", "earned": False, "progress": 2, "target": 4, "hint": "혈압 4번 기록"},
    {"code": "cycle_1", "label": "1차 4주 완주", "group": "record", "earned": False, "progress": 0, "target": 1, "hint": "1차 4주를 마쳐요"},
    {"code": "cycle_12w", "label": "12주 완주", "group": "record", "earned": False, "progress": 0, "target": 1, "hint": "12주를 마쳐요"}]}

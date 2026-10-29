-- 체험(10/22~10/25) 집계. 읽기만 한다. 운영 DB에서 삭제 전에 한 번 돌려 숫자를 확정한다.
-- 실행(한글 비교가 있어서 반드시 utf8mb4로): docker compose exec -T mysql sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < docs/사용자테스트/체험_집계.sql
-- 주의: 서버 MySQL이 한글을 latin1로 받으면 '[체험 자동 채움]%' 비교가 0건으로 세진다(10/26에 겪음).
-- 이메일은 암호화돼 있어 SQL로 팀원을 가릴 수 없다. 팀원 계정은 user_id 끝 8자리로 뺀다(체험_설문_중간정리_1026.md 기준).
-- 가입 시각은 UTC라 한국 10/22 00:00 = UTC 10/21 15:00.

SET @from = '2026-10-21 15:00:00';   -- 체험 시작(한국 10/22 00:00)
SET @to   = '2026-10-25 15:00:00';   -- 체험 종료(한국 10/26 00:00)

DROP TEMPORARY TABLE IF EXISTS cohort;
CREATE TEMPORARY TABLE cohort AS
SELECT user_id FROM users
WHERE status = 'active' AND created_at >= @from AND created_at < @to
  AND RIGHT(user_id, 8) NOT IN ('3df91e73', '11f6778e', 'a59c5793', '5249ef14')
  AND user_id NOT IN (SELECT account_id FROM access_logs WHERE 0);   -- 자리 표시(관리자 제외는 admin 계정이 이 기간 가입자가 아니라 불필요)

-- 0. 코호트 수 (기대: 26, 중복 가입 1명은 따로 빼야 하면 여기서 확인)
SELECT 'cohort' AS item, COUNT(*) AS n FROM cohort;

-- 1. 사람별 직접 기록한 날 수 (자동 채움 기록 제외)
DROP TEMPORARY TABLE IF EXISTS own_days;
CREATE TEMPORARY TABLE own_days AS
SELECT c.user_id, COUNT(DISTINCT l.log_date) AS days
FROM cohort k
JOIN challenge_cycles c ON c.user_id = k.user_id
JOIN cycle_challenges x ON x.cycle_id = c.cycle_id
JOIN challenge_logs l ON l.cycle_challenge_id = x.cycle_challenge_id
WHERE l.note IS NULL OR l.note NOT LIKE _utf8mb4'[체험 자동 채움]%'
GROUP BY c.user_id;

-- 2. 챌린지 시작자 중 직접 기록한 날 수 분포 (기대: 시작 19명, 3일 이상 8명, 첫 3일 못 넘김 11명)
SELECT 'challenge_started' AS item, COUNT(DISTINCT c.user_id) AS n
FROM cohort k JOIN challenge_cycles c ON c.user_id = k.user_id
UNION ALL
SELECT '직접 3일 이상', COUNT(*) FROM own_days WHERE days >= 3
UNION ALL
SELECT '시작했지만 3일 미만(기록 0일 포함)',
       (SELECT COUNT(DISTINCT c.user_id) FROM cohort k JOIN challenge_cycles c ON c.user_id = k.user_id)
       - (SELECT COUNT(*) FROM own_days WHERE days >= 3);

SELECT days AS 직접기록일수, COUNT(*) AS 인원 FROM own_days GROUP BY days ORDER BY days;

-- 3. 4주 결과를 받은 사람(사이클이 끝남) / 다음 4주를 시작한 사람
SELECT '4주 사이클 끝남' AS item, COUNT(DISTINCT c.user_id) AS n
FROM cohort k JOIN challenge_cycles c ON c.user_id = k.user_id
WHERE c.status IN ('completed', 'incomplete')
UNION ALL
SELECT '다음 4주 시작(2차 이상)', COUNT(DISTINCT c.user_id)
FROM cohort k JOIN challenge_cycles c ON c.user_id = k.user_id
WHERE c.cycle_number >= 2;

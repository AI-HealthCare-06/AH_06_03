# 배포 인프라 노트 (작성: 효민 · 최초 2026-09-30 · 갱신 2026-10-13)

> 이 문서는 "서버에 무슨 일이 생겼을 때 효민님 없이도 팀원이 참고할 수 있게" 만든 기록입니다.
> **실제 비밀번호·키·웹훅 주소는 여기 안 적습니다.** 저장 위치만 안내합니다.
> 서버 시각은 **UTC**입니다. 한국 시간은 +9시간입니다 (예: 서버 18:00 = 한국 새벽 3시).

## 목차

1. 서버 기본 정보 · 2. SSH · 3. 서비스 구성 · 4. 배포 주소 · 5. 배포 방법 · 6. 롤백 · 7. DB · 8. 백업과 복구 · 9. 트러블슈팅 · 10. 점검 알림 · 11. 서버 정기 관리 · 12. 보안 약속 · 13. 알아두면 좋은 것 · 14. 남은 일

---

## 1. 서버 기본 정보

| 항목 | 값 |
|---|---|
| 리전 | 아시아 태평양(서울), ap-northeast-2 |
| 인스턴스 타입 | t3.small (최초 t3.micro가 메모리 부족이라 업그레이드, §9 참고) |
| 고정 IP (Elastic IP) | `54.116.113.17` — 서버를 껐다 켜도 안 바뀜 |
| OS | Ubuntu 26.04 LTS (2026-10-08에 보안 업데이트와 재부팅, §11) |
| 루트 디스크 | 19GB |
| 접속 계정 | `ubuntu` |

## 2. SSH 접속 방법

```bash
ssh -i ~/Downloads/paeon-new ubuntu@54.116.113.17
```

- 키 파일(`paeon-new`)은 **효민님 컴퓨터에만 보관**. 절대 채팅·깃허브·디스코드 등에 올리지 않기.
- 서버에 등록된 SSH 공개키는 **1개**(`paeon-new`)뿐임. 예전 키는 유출 사고로 폐기하고 서버에서 제거함.
- 보안 그룹의 SSH(22)는 **"위치 무관(0.0.0.0/0)"으로 유지**. GitHub Actions가 매번 다른 IP에서 접속해서, 특정 IP로 좁히면 자동 배포가 깨짐. 키 인증이 실제 방어선.

## 3. 서비스 구성 (`docker-compose.yml`)

서버의 `~/AH_06_03`에 컨테이너 3개가 떠 있고, 셋 다 `restart: unless-stopped`(죽으면 자동 재시작, 서버 재부팅 후에도 자동 기동)임.

| 서비스 | 역할 | 비고 |
|---|---|---|
| `caddy` | HTTPS 종료, `frontend/` 정적 화면 서빙, API 경로만 fastapi로 전달 | 80, 443 (밖에서 접속 가능) |
| `fastapi` | 백엔드 API, uvicorn 단일 프로세스(`--reload` 없음, `exec`로 실행해 종료 신호를 앱이 직접 받음) | 메모리 상한 1GB, 밖에서 직접 접속 불가 |
| `mysql` | DB (MySQL 8.0), 데이터는 이름 붙은 볼륨에 보존 | 밖에서 직접 접속 불가 |

### 밖에 열려 있는 문 (보안 그룹, 2026-10-12 기준, 밖에서 확인함)

| 포트 | 상태 | 이유 |
|---|---|---|
| 22 (SSH) | 열림 | 서버 접속, GitHub Actions 자동 배포 |
| 80 (HTTP) | 열림 | HTTPS로 넘기는 용도 |
| 443 (HTTPS) | 열림 | 공개 화면과 API |
| 3306 (MySQL) | **닫힘** | 앱은 컨테이너 내부 네트워크로 접속하므로 불필요 |
| 8000 (FastAPI 직접) | **닫힘** | Caddy(443)를 거치지 않는 암호화 없는 통로라 닫음 |
| 5432 | 닫힘 | 사용하지 않음 |

- compose 파일이 호스트에 3306, 8000을 연결해 두지만, **보안 그룹이 막고 있으니 규칙을 다시 열지 말 것**. 열어야 할 이유가 생기면 팀에 먼저 알리기.
- 로컬 개발(`127.0.0.1:8000`)은 이 보안 그룹과 무관해서 그대로 동작함.
- 밖에서 확인하는 방법(맥북): `nc -z -w 3 54.116.113.17 3306 && echo 열림 || echo 닫힘` (포트 번호만 바꿔서)

## 4. 배포 주소

- **공개 주소(HTTPS)**: `https://54-116-113-17.sslip.io` — 앱 시작 화면(`index.html`)
- **API 문서(Swagger)**: `https://54-116-113-17.sslip.io/docs`
- `sslip.io`는 도메인을 사지 않고 IP를 도메인처럼 쓰게 해주는 무료 서비스. Caddy가 Let's Encrypt 인증서를 자동 발급·갱신함.

### Caddy가 요청을 나누는 방식 (`Caddyfile`)

- 아래 경로만 fastapi로 전달: `/v1/*`, `/docs`, `/docs/*`, `/openapi.json`, `/healthcheck`, `/static/*`, `/media/*`
- 나머지는 `frontend/` 폴더의 정적 파일을 그대로 서빙 (compose에서 `./frontend:/srv/frontend:ro`로 연결).
- **새 API 경로를 `/v1` 밖에 만들면 Caddyfile의 `@api` 목록에 추가해야 함.** 안 하면 화면 파일로 처리돼 404가 남.
- 화면과 API가 같은 주소(같은 출처)라서 CORS 설정이 필요 없음.
- `frontend/`의 변경은 main에 머지되면 화면에 자동 반영됨. 안 바뀌어 보이면 강력 새로고침(Cmd+Shift+R).
- `Caddyfile`만 바꾼 배포는 컨테이너가 안 바뀌어 반영이 안 될 수 있음 → 그때는 `sudo docker compose restart caddy`.

## 5. 배포 방법

### 자동 배포 (기본)

`main`에 머지(또는 push)되면 `.github/workflows/deploy.yml`이 순서대로 실행함.

1. GitHub Actions가 SSH로 서버에 접속
2. `git pull origin main`
3. `docker compose up --build -d` (이미지 빌드, 컨테이너 재기동)
4. 24시간 지난 빌드 캐시 정리 (`docker builder prune -f --filter until=24h || true`, 실패해도 배포는 계속)
5. `alembic upgrade head` (DB 마이그레이션 자동 적용)
6. 성공·실패를 디스코드로 알림

- 배포는 `concurrency`로 **한 번에 하나씩** 실행됨(진행 중인 배포는 끊지 않고 다음 배포가 대기). 그래도 연달아 머지할 땐 앞 배포가 "배포 성공"으로 끝난 뒤에 머지하는 게 안전함.
- **마이그레이션이 든 PR은 머지하는 순간 서버 DB에 적용됨.** 로컬에서 충분히 테스트하고, 머지 직전에 서버에서 `bash ~/paeon-monitor/backup.sh`로 백업을 한 번 뜰 것(§8).
- 앱 코드가 아니라 `deploy.yml`만 바꾼 배포는 컨테이너가 바뀌지 않음(확인됨).
- 확인: 저장소 **Actions 탭**(초록 체크 = 성공), 디스코드 알림. 단 "배포 성공"은 스크립트가 끝났다는 뜻이지 앱이 정상이라는 뜻은 아님 → 중요한 배포 뒤에는 `curl https://54-116-113-17.sslip.io/v1/consent-policies/active`가 200인지, 화면에서 로그인이 되는지 한 번 확인.

### 배포 때 API가 끊기는 시간 (실측)

- **앱 코드만 바뀌는 배포**(fastapi만 다시 만들어짐): API가 약 **4~5초** 끊김. 밖에서 1초 간격으로 `/healthcheck`를 쟀을 때 502가 4~5번 나옴(2026-10-12). 그 사이 화면 파일은 계속 보이고 API 호출만 실패함 → 새로고침하면 됨.
- fastapi 컨테이너를 다시 만드는 시간(`docker compose up -d --force-recreate fastapi`): **1.9초** (종료 신호 수정 전에는 11.5초, §9).
- `.env`나 compose 설정이 바뀌어 mysql까지 다시 만들어지면 더 길 수 있음(재어 보지 않음. 2026-10-07 비밀번호 교체 때 1분 남짓으로 추정). DB 데이터는 볼륨에 그대로 있음.

### 수동 배포 (Actions가 안 될 때만)

```bash
ssh -i ~/Downloads/paeon-new ubuntu@54.116.113.17
cd ~/AH_06_03
git pull origin main
sudo docker compose up --build -d
sudo docker compose exec -T fastapi alembic upgrade head
sudo docker compose ps   # 전부 Up(fastapi, mysql은 healthy)인지 확인
```

### 로컬 개발 참고

`--reload`를 뺐으므로 코드를 고친 뒤에는 `docker compose restart fastapi`로 반영함.

## 6. 롤백 (배포가 깨졌을 때)

### 어떤 경로를 쓰나

| 상황 | 경로 | 걸리는 시간 |
|---|---|---|
| 기본: 문제 PR을 되돌릴 때 | GitHub에서 그 PR의 **Revert** 버튼으로 되돌리는 PR을 만들어 머지 → 자동 배포 | 3~5분 추정. 가장 안전 |
| 긴급: 서버가 지금 깨졌을 때 | 서버의 `rollback.sh`로 코드를 이전 커밋으로 되돌림 | **21초** (2026-10-12 연습, DB 백업 포함) |
| DB 마이그레이션이 문제일 때 | 코드 롤백으로는 안 풀림 → §8의 백업 복구가 필요할 수 있음 | 이 문서에는 연습한 절차가 없음. 효민과 함께 진행 |

### 사고 났을 때 순서

1. 팀에 "배포가 깨졌어요. main 머지 멈춰 주세요."
2. 서버에서 마지막으로 정상이던 커밋을 골라 되돌리기:
   ```bash
   bash ~/paeon-monitor/rollback.sh                  # 최근 커밋 목록만 봄
   bash ~/paeon-monitor/rollback.sh 해시              # 계획만 봄 (아무것도 안 바뀜)
   bash ~/paeon-monitor/rollback.sh 해시 --yes        # 실제로 되돌림
   ```
3. GitHub에서 문제 PR을 Revert하는 PR을 만들어 머지 (**꼭 필요**. 아래 주의 참고)
4. 머지한 배포가 초록이면 "머지 재개"

### 스크립트가 지켜 주는 것

- 기본은 **계획만 보기**. `--yes`를 붙여야 실행됨.
- 현재 코드의 과거가 아닌 커밋(다른 가지)은 거절함.
- 서버 폴더에 커밋 안 된 수정이 있으면 지우지 않고 멈춤.
- 되돌릴 구간에 **DB 마이그레이션이 있으면 거절**함. `--db-ahead-ok`를 붙여야 코드만 되돌리고, DB는 이 스크립트가 건드리지 않음.
- 실행 전에 DB 백업을 한 번 뜨고, 백업이 실패하면 중단함(`--skip-backup`으로 건너뛸 수 있음).
- 끝나면 fastapi 상태, `healthcheck`, DB 경유 API를 확인하고, 시작과 완료를 디스코드로 알림.

### 주의

- 긴급 롤백은 **서버만 뒤로 돌림**. 서버가 main보다 뒤에 있는 동안 다른 PR이 머지되면 다음 배포가 최신(나쁜 커밋 포함)으로 다시 올려서 **롤백이 조용히 취소됨**. 그래서 롤백 전에 머지를 멈추고 이어서 Revert PR을 머지해야 함.
- 너무 많이 되돌리면 그 사이 고친 버그가 되살아남.
- 롤백한 뒤 원래대로 올리려면:
  ```bash
  cd ~/AH_06_03
  git pull origin main
  sudo docker compose up --build -d
  ```
- `git reset --hard`를 쓰므로 서버 폴더의 커밋 안 된 수정은 지워짐(수정이 있으면 스크립트가 멈춤).
- **마이그레이션이 든 PR은 GitHub의 Revert로 되돌리지 말 것.** 이미 서버 DB에 적용된 마이그레이션 파일이 저장소에서 사라지면, 서버 DB의 버전 기록이 없는 파일을 가리켜서 이후 모든 배포의 `alembic upgrade head`가 `Can't locate revision`으로 실패함(작은 시험 환경에서 확인). 문제가 생기면 앞으로 고치는 새 PR을 올리고, 정말 되돌릴 때는 서버에서 `alembic downgrade 이전번호`를 **먼저** 한 뒤에 코드를 Revert할 것.
- 마이그레이션이 든 PR이 동시에 여럿이면 **한 줄로 이어지게** 해야 함. 둘 다 같은 번호 뒤에 붙으면 마이그레이션 머리가 둘이 되어 배포가 실패함. 머지 순서를 정하고, 뒤 PR의 `down_revision`을 앞 PR의 마지막 번호로 맞출 것.
- 연습 기록(2026-10-12): 백엔드 4개 파일 구간을 되돌려 21초에 끝났고, `git pull`이 충돌 없이 fast-forward로 최신에 복귀함.

## 7. DB

- DB명 `paeon`, 앱 계정 `paeon`. 앱은 컨테이너 내부 네트워크로 `mysql:3306`에 접속함.
- **서버 밖에서는 DB에 직접 접속할 수 없음**(3306 닫힘). 확인이 필요하면 서버에 SSH로 들어가서 `sudo docker compose exec mysql ...`로 접속.
- 비밀번호는 서버의 `~/AH_06_03/.env`에만 있음(`DB_PASSWORD`, `DB_ROOT_PASSWORD`). `.env`는 `.gitignore`에 있어 깃허브에 안 올라가고, **값은 채팅이나 문서에 붙여넣지 않음**.
- 2026-10-07에 root와 앱 계정 비밀번호를 새 값으로 교체함. 값은 서버 안에서 만들었고 옛 비밀번호가 차단되는 것을 확인함.
- 비밀번호 교체 원칙: 서버 안에서 생성 → 값을 명령줄에 쓰지 않고 입력 스트림으로 `ALTER USER` → `.env` 갱신 → `docker compose up -d --force-recreate fastapi` → 옛 비밀번호가 막혔는지, `alembic current`가 동작하는지 확인.
- **DB를 볼 때는 값이 아니라 개수만 출력하는 쪽으로.** 건강정보가 들어 있으므로 `SELECT *`로 값을 화면에 띄우거나 채팅에 붙이지 않음. 한 사용자의 표별 행 수는 `bash ~/paeon-monitor/user_rows.sh 이메일 또는 user_id`로 볼 수 있음(개수만 출력).

### 회원 탈퇴가 하는 일 (코드를 읽고 서버에서 실제로 확인함, 2026-10-12)

- 개인 데이터 표(`user_id` 칸이 있는 13개)의 그 사용자 행을 **삭제**하고, 그 아래 자식 표(측정값, 설문 답, 예측 요인, 챌린지 기록)는 DB의 연쇄 삭제로 같이 지워짐.
- `users` 행은 **지우지 않고** 이메일을 `deleted+{id}@invalid`로 바꾸고 비밀번호를 무력화해서 남김(상태 `deleted`). 탈퇴 기록(`account_deletion_requests`)에는 표별로 지운 개수가 남음. → "계정 기록이 아예 삭제된다"는 정확한 설명이 아님.
- 서버에서 설문, 예측, 챌린지, 캘린더까지 채운 계정으로 시험해 모두 0건이 되는 것을 확인함. 아직 시험하지 않은 표: `health_todos`, `guardian_consent_verifications`.
- **백업(서버 7개, 맥북 사본)과 스냅샷에는 탈퇴 전 데이터가 남음.** 탈퇴 시 백업에서도 지워야 하는지는 정책으로 정할 것(§14).

### 테스트 계정 일괄 삭제 (혜림님 작성, `app/scripts/purge_test_accounts.py`)

- 서버에서 컨테이너 안으로 실행: `sudo docker compose exec -T fastapi python -m app.scripts.purge_test_accounts --pattern "%@example.com"`
- 기본은 **미리보기**: 지울 대상만 보여 주고 아무것도 안 지움. 진짜 지우려면 같은 명령에 `--apply`를 붙임.
- 이메일 패턴(LIKE)에 맞는 **탈퇴 안 한 계정**을 회원 탈퇴와 같은 규칙으로 삭제함(개인 데이터 삭제, 계정 행은 이메일을 가려 남김). `%@%`처럼 너무 넓은 패턴은 거절하지만 `%@gmail.com` 같은 패턴은 통과하므로, **미리보기 목록에 팀원·관리자 계정이 없는지 눈으로 확인한 뒤** `--apply`할 것.
- 서버에서 미리보기까지 확인함(2026-10-13). 실제 삭제(`--apply`)는 서버에서 아직 안 돌려 봄.
- 앱 안의 데이터만 지움. 서버 백업, 디스크 스냅샷, 맥북 사본은 §14의 삭제 순서로 따로 지워야 함.

### 가입·수정 시각(`created_at`) 주의

- 2026-10-12 05:16(UTC) 이전에 만들어진 `users`, `user_profiles` 행의 `created_at`, `updated_at`은 **가입 시각이 아니라 앱이 켜진 시각**으로 찍혀 있음(수정 전 버그, `TimestampMixin`). 그 이후 가입한 계정은 실제 시각으로 찍힘. 분석에서 이 값을 쓸 때 주의.

## 8. 백업과 복구

### 자동 백업

- 서버의 `~/paeon-monitor/backup.sh`가 cron으로 **매일 18:00(UTC, 한국 새벽 3시)** 실행됨.
- 결과: `~/backups/paeon-날짜-시각.sql.gz`, **최근 7개만 보관**(권한 600, 폴더 700).
- 덤프가 끝까지 만들어졌는지 검사하고, 실패하면 디스코드로 알림. 실패한 날에는 파일이 안 생겨서 기존 좋은 백업이 지워지지 않음.
- 백업이 **36시간 넘게 안 갱신되면** 점검 스크립트가 경고함(§10).
- 수동으로 지금 한 번 뜨기: `bash ~/paeon-monitor/backup.sh` (마이그레이션 PR을 머지하기 전에 권장).
- **마이그레이션 전에 뜬 백업은 최신 구조가 아님.** 복원하면 `alembic_version`도 그때 값으로 돌아가므로, 복구할 때는 코드와 DB 구조가 맞는지 확인해야 함(시험으로 확인한 사실, 2026-10-08).

### 복원이 되는지 확인하는 방법 (실제 DB는 안 건드림)

임시 MySQL 컨테이너에만 복원해서 확인함. **실제 DB에 바로 덤프를 넣지 말 것.**

```bash
cd ~/AH_06_03
B=$(ls -t ~/backups/paeon-*.sql.gz | head -1); echo "$B"
sudo docker rm -fv restore-test >/dev/null 2>&1
sudo docker run -d --name restore-test --memory 512m --memory-swap 512m -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=paeon_restore mysql:8.0 --innodb-buffer-pool-size=64M --performance-schema=OFF --skip-log-bin
# 준비될 때까지 기다림 (서버가 3306으로 떴다는 로그와 DB 존재를 둘 다 확인)
ok=""; for i in $(seq 1 60); do if sudo docker logs restore-test 2>&1 | grep -q "ready for connections.*port: 3306" && sudo docker exec restore-test mysql -uroot -N -e "SHOW DATABASES" 2>/dev/null | grep -qx paeon_restore; then ok=1; break; fi; sleep 2; done
[ -n "$ok" ] && time (gunzip -c "$B" | sudo docker exec -i restore-test mysql -uroot paeon_restore)
# 확인이 끝나면 반드시 지우기 (지인 입력값이 들어 있음). -v를 빼면 복원한 DB가 안 쓰는 볼륨으로 남음
sudo docker rm -fv restore-test
```

- 시험 결과(2026-10-08): 29개 표를 복원해 실제 DB와 행 수가 모두 일치함. 복원 약 1.9초(당시 데이터 규모 기준).
- 임시 컨테이너 준비를 로그의 `ready for connections` 개수로 판단하면 초기화 중에 복원을 시도해 `Unknown database` 오류가 남(위처럼 포트와 DB 존재를 같이 확인할 것).
- **실제 DB를 되돌리는(복구하는) 절차는 연습한 적이 없음.** 필요하면 효민과 함께 진행.

### 서버 밖 사본

- 효민의 맥북에 암호화한 사본이 있음(AES-256). 암호는 맥 키체인과 비밀번호 관리자에 있고 값은 문서에 없음. 주기적인 자동 반출은 아직 없음(S3 등은 미구현).
- 백업 파일에는 **사용자가 입력한 건강정보가 들어 있음.** 채팅, 깃허브, 디스코드에 올리지 말 것.

## 9. 트러블슈팅 기록 (같은 문제가 또 생기면 참고)

### 컨테이너가 갑자기 꺼져 있음 / 502 / `Killed` → 메모리 부족(OOM)
- 증상: `docker compose ps -a`에서 fastapi가 `Exited (137)`, 사이트 502, caddy 로그에 `lookup fastapi ... server misbehaving`.
- 확인: `sudo dmesg -T | grep -i "killed process"`, `free -h`, `sudo docker top ah_06_03-fastapi-1 -eo pid,ppid,rss,comm`(프로세스별 메모리). 재부팅하면 `dmesg` 기록이 사라지므로 필요하면 먼저 저장.
- 1차(t3.micro): RAM 908MiB에 스왑 없음 → 스왑 추가 + t3.small(RAM 2GB)로 업그레이드.
- 2차(t3.small에서도 반복): uvicorn이 약 1.5GB까지 커져 종료됨. 프로세스별로 재 보니 `--reload` 감시용 uvicorn이 요청이 없어도 3분에 107MB씩 늘었음(재시작 직후 558MB vs 앱 92MB). `--reload` 제거 뒤에는 uvicorn 하나가 93MB로 3분간 변화 없음.
- 안전망: `restart: unless-stopped`, fastapi `mem_limit`/`memswap_limit` 1g.
- 이후 관찰(2026-10-12 기준): 10/8 재부팅 뒤 약 4일간 커널 OOM 기록 없음. 부하 시험(동시 10명, 약 9천 건)에서 fastapi 메모리가 88MiB에서 약 98MiB로 올랐다가 더 오르지 않음. 몇 시간 이상의 장시간 시험과 DB를 쓰는 정식 예측 흐름은 아직 시험하지 않음.

### 로그인·가입이 몰리면 서버 전체가 느려짐 (수정됨, 2026-10-12)
- 원인: 비밀번호 해시(bcrypt)가 `async def` 안에서 동기로 호출돼, 한 번에 약 0.3초(서버에서 301ms) 동안 이벤트 루프를 막음. uvicorn 일꾼이 1개라 그동안 모든 요청이 같이 대기.
- 재현(수정 전): 예측 6명 + 로그인 2명 → 예측이 초당 197건에서 22.7건으로 감소, p95 44ms에서 636ms. 예측 1명 + 로그인 8명 → 로그인 응답 p50 2,370ms, 같은 때 예측 요청은 p50 3,973ms.
- 조치: bcrypt를 `asyncio.to_thread`로 옮김(PR #60).
- 재측정(수정 후): 예측 초당 126건, p95 83ms. 로그인 8명이 몰린 동안 예측 p50 29ms. 로그인 처리량은 초당 3.3건에서 5.5건으로 늘어 두 코어를 쓰는 것으로 보임.
- 남은 한계: 로그인 한 번의 CPU 비용(약 0.3초)은 그대로라 한꺼번에 많이 가입하면 로그인 응답이 1~2초로 느려질 수 있음. 부하 시험 스크립트는 효민 맥북의 `~/loadtest.py`(저장소에는 없음).

### 컨테이너를 다시 만들 때 10초가 걸림 (수정됨, 2026-10-12)
- 원인: fastapi가 `sh -c "uvicorn ..."`로 시작해 컨테이너의 1번 프로세스가 `sh`였음(`/proc/1/cmdline`로 확인). 도커의 종료 신호(SIGTERM)가 uvicorn에 전달되지 않아 기본 10초를 기다렸다가 강제 종료됨(처리 중이던 요청도 끊김).
- 조치: compose의 entrypoint를 `sh -c "exec uvicorn ..."`로 변경.
- 결과: `docker compose up -d --force-recreate fastapi`가 11.5초에서 1.9초로 줄음. 사용자가 겪는 끊김(4~5초)은 비슷함.
- 확인 방법: `sudo docker exec ah_06_03-fastapi-1 sh -c "tr '\0' ' ' < /proc/1/cmdline; echo"`가 `uvicorn app.main:app ...`으로 바로 시작하면 정상.

### 앱은 살아 있는데 DB가 안 될 때 (`/healthcheck`는 200)
- 원인: `/healthcheck`는 DB를 확인하지 않고 항상 `ok`를 돌려줌. docker의 healthy 판정도 이것만 봄.
- 대응: 점검 스크립트에 DB를 읽는 공개 API(`/v1/consent-policies/active`, 로그인 불필요)가 200인지 보는 항목을 추가함(§10). 수동 확인은 `curl -s -o /dev/null -w '%{http_code}\n' https://54-116-113-17.sslip.io/v1/consent-policies/active`.

### 디스크가 이유 없이 늘어남 → 안 쓰는 볼륨 (2026-10-13 발견)
- 원인: 복원 시험용 임시 MySQL을 `docker rm -f`로만 지우면 컨테이너는 사라져도 **데이터 볼륨(익명 볼륨)이 남음**. 복원한 DB 사본(지인 입력값 포함)이 약 210MB씩 쌓여 4개(약 840MB)가 남아 있었음. 이후 절차를 `docker rm -fv`로 고침.
- 확인: `sudo docker system df`의 Local Volumes에서 RECLAIMABLE이 큰지, `sudo docker volume ls -f dangling=true`.
- 정리: 목록의 이름이 64자리 무작위 글자(익명)인지 확인한 뒤 `sudo docker volume prune -f`. 도커 23 이상에서는 이름 없는(익명) 안 쓰는 볼륨만 지움. 이름 붙은 볼륨(DB 데이터)은 이 명령으로 지워지지 않지만, 목록을 먼저 보고 할 것.

### 디스크 공간 부족 (`No space left on device`)
```bash
sudo docker system df          # 뭐가 용량을 먹는지 확인 (보통 Build Cache)
sudo docker builder prune -f   # 안 쓰는 빌드 캐시 정리
df -h /                        # 정리 후 남은 용량 확인
```
- 24시간 지난 캐시는 배포 때 자동으로 정리됨. 실행 중인 컨테이너와 DB 볼륨은 이 명령으로 지워지지 않음.
- 배포가 도는 중에는 정리하지 말 것(빌드와 부딪힐 수 있음).

### 배포 실패: `Conflict. The container name ... is already in use`
- 원인: PR을 연달아 머지해서 배포 두 개가 서버에서 겹침.
- 대응: 컨테이너를 지우거나 Re-run 하기 전에 먼저 서버 상태 확인(`sudo docker ps -a`). 이미 정상일 수 있음.
- 재발 방지: `concurrency`로 배포 직렬화, 앞 배포가 끝난 뒤 머지.

### `ModuleNotFoundError: No module named 'paeon_models'`
- 원인: `modeling/` 폴더가 Docker 이미지에 안 들어가고 있었음.
- 조치: `app/Dockerfile`에 `COPY modeling ./modeling`과 `PYTHONPATH` 추가.

### `docker-compose.yml`을 고친 뒤 `depends_on` 중복 키 에러
- 원인: nano로 고치다 붙여넣은 블록이 다른 서비스 안으로 섞임.
- 조치: 파일 전체를 `cat > file << 'EOF' ... EOF`로 통째로 다시 쓰기.

### 서버 재부팅(Stop → Start) 후
- `restart: unless-stopped` 덕분에 컨테이너가 자동으로 올라옴(2026-10-08 재부팅에서 1분 안에 healthy 확인). 그래도 `sudo docker compose ps`로 확인.
- Elastic IP라 주소는 그대로(`54.116.113.17`).

## 10. 점검 알림 (모니터링)

서버가 조용히 죽는 일을 막기 위한 점검. **이상이 있을 때만 디스코드로 알림**이 오고, 정상일 땐 아무것도 안 옴.

- 위치: 서버의 `~/paeon-monitor/check.sh` (저장소에는 없음), cron으로 5분마다 실행.
- 웹훅 주소는 서버의 `~/.monitor.env`(권한 600, 저장소에 없음). 주소가 노출되면 디스코드에서 웹훅을 지우고 새로 만들어 이 파일을 교체.

| 점검 | 알림 조건 |
|---|---|
| 디스크 | 80% 이상 |
| 메모리 | 여유(available)가 250MB 미만 |
| 사이트 | `/healthcheck`가 200이 아님 |
| 컨테이너 3개 | 꺼짐, unhealthy, 없음 |
| 자동 재시작 | 재시작 횟수가 늘면 즉시 알림 |
| 백업 | 가장 최근 백업이 36시간 넘음 (또는 백업 파일이 없음) |
| DB 경유 API | `/v1/consent-policies/active`가 200이 아님 (앱은 살아 있는데 DB가 안 되는 경우를 잡음) |

- 같은 문제가 2번 연속(약 5~10분) 이어질 때만 경고하고, 계속되면 60분마다 다시 알리고, 풀리면 복구 알림. 배포 중 컨테이너가 잠깐 바뀌어도 오경보가 안 나게 한 규칙.
- 연결 시험: `bash ~/paeon-monitor/check.sh test` → `204`가 나오고 채널에 테스트 메시지가 오면 정상.
- 경보 시험(팀에 알림이 가지 않는 방법): 가짜 웹훅과 임시 폴더로 돌림.
  ```bash
  rm -rf /tmp/dbtest; mkdir -p /tmp/dbtest
  echo 'DISCORD_WEBHOOK="http://127.0.0.1:9/none"' > /tmp/dbtest/fake.env
  ENV_FILE=/tmp/dbtest/fake.env STATE_DIR=/tmp/dbtest/s1 DB_CHECK_URL=https://54-116-113-17.sslip.io/v1/nothing-here bash ~/paeon-monitor/check.sh
  ls /tmp/dbtest/s1      # db_api.cnt가 있으면 이상을 잡은 것
  rm -rf /tmp/dbtest
  ```
- 끄기: `crontab -l | grep -v paeon-monitor | crontab -`
- 한계: 서버 전체가 꺼지면 이 점검도 멈춰서 알릴 수 없음(외부에서 보는 점검은 아직 없음). 실제로 DB를 깨서 경고가 가는지는 시험하지 않음.

## 11. 서버 정기 관리 (OS 업데이트와 재부팅)

- 서버에 접속했을 때 `*** System restart required ***`가 뜨면 업데이트가 설치됐고 재부팅이 필요한 상태.
- 2026-10-08에 한 순서 (예상 중단 2~4분, 재 본 값은 아님):
  1. 팀에 알림, GitHub Actions에 도는 배포가 없는지 확인
  2. 필요하면 `sudo dmesg -T | grep -i "killed process" > ~/oom-history.txt`로 OOM 기록 저장 (재부팅하면 사라짐)
  3. AWS 콘솔에서 루트 볼륨 **스냅샷** 생성(완료될 때까지 대기)
  4. `sudo apt update`, 업그레이드:
     ```bash
     sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
     ```
     (Docker가 업데이트되면 컨테이너가 한 번 재시작되고 자동으로 올라옴)
  5. 재부팅 전 점검: `sudo dpkg --audit`(출력 없음), `systemctl --failed --no-pager`(0개), `ls /boot | grep -E "vmlinuz|initrd"`(새 커널 있음), `sudo grep -c "새커널버전" /boot/grub/grub.cfg`(1 이상)
  6. `sudo reboot` → 접속 가능해질 때까지 기다림
  7. 확인: `uname -r`(새 커널), `ls /var/run/reboot-required`(없음), `sudo docker compose ps`(전부 Up, fastapi·mysql healthy), 밖에서 포트와 `healthcheck`
- 스냅샷은 문제가 없는 걸 보고 며칠 뒤 지움(저장 용량만큼 소액 비용).
- 일부 업데이트는 단계적으로 배포돼서 `apt list --upgradable`에 며칠 남아 있을 수 있음.

## 12. 보안 약속

- 밖에 열린 문은 **22, 80, 443**만. 규칙을 추가하기 전에 팀에 알리기. DB 포트는 열지 않고, DB 확인은 SSH로.
- 키, `.env` 값, 웹훅 주소, 토큰, 백업 파일은 채팅·깃허브·디스코드에 붙여넣지 않음. **노출되면 지체 없이 폐기하고 새로 만듦.**
- `GUARDIAN_ENC_KEY`와 백업 암호는 잃어버리면 보호자 정보와 백업을 못 여니, 서버 밖에 별도로 보관해 둠(담당: 효민, 맥 키체인과 비밀번호 관리자에 사본, 해시 지문 비교로 일치 확인). 값은 문서에 적지 않음.
- 서버에서 직접 고친 설정은 저장소에 반영(커밋)할 것. `main`에는 직접 push하지 않고 PR로 합치기로 함. GitHub의 main 보호 규칙은 켜지 않기로 했고(팀 결정, 2026-10-13), PR과 리뷰 관행으로 지킴. 직접 push가 기술적으로 막혀 있지는 않아서, 서버가 깨지면 §6의 롤백으로 복구함.
- 사용자(지인) 입력값은 건강정보이므로, DB를 확인할 때 값 대신 개수만 보고 필요한 사람만 접근함.
- **저장소는 공개(Public)**: 코드, 문서, PR, Actions 로그를 누구나 볼 수 있음. 비밀값, 실제 사용자 데이터, 서버 접속 키는 올리지 않음. 2026-10-13에 전체 기록(커밋 243개, 브랜치 20개)을 훑어 개인 키, AWS 키, 웹훅 주소, 토큰 모양과 `.env` 파일이 없음을 확인함(`.env.example`의 값은 `change-me`뿐). 검사 범위는 1MB 미만 파일과 위 패턴이라 완전한 보증은 아님.
- **저장소 권한**: 직접 접근 권한자 4명(모두 admin, 1명은 외부 협업자). 쓰기 권한이 있으면 배포 워크플로를 통해 서버에 명령을 실행할 수 있어서, 이 4명이 "서버를 관리하거나 서비스를 올릴 수 있는 사람"임(개인정보 방침의 N=4). 서버에 직접 접속하는 SSH 키를 가진 사람은 1명이고, 비밀번호 접속은 막혀 있음(`passwordauthentication no`, 2026-10-13 확인).

## 13. 알아두면 좋은 것

- GitHub Secrets: `EC2_HOST`(=54.116.113.17), `EC2_SSH_KEY`(서버 접속 키), `DISCORD_WEBHOOK`(배포 알림용).
- 서버 변경은 가능하면 PR로 합의하고 한 PR로 묶어 머지 횟수를 줄이기.
- **관리자 화면**(`https://54-116-113-17.sslip.io/admin.html`, 메뉴에 링크 없이 주소로만): 챌린지 미션의 노출(켬/끔)과 카테고리 순서를 바꿈. 서버 `.env`의 `ADMIN_EMAILS`(쉼표로 구분한 이메일, 비면 아무도 못 씀)에 있는 계정이 평소 로그인으로 들어와서 씀. 목록을 바꾼 뒤에는 `sudo docker compose up -d --force-recreate fastapi`가 필요함(약 5초 끊김). **이메일 인증이 없어서 먼저 가입된 계정만 목록에 넣을 것**(가입 전 이메일을 넣으면 다른 사람이 먼저 가입해 관리자가 될 수 있음). 바꾼 내용은 서버 로그에 남음. 고정 미션(금연·절주)은 규칙이 정해서 스위치가 없음.
- 서버에서 도는 도구는 `~/paeon-monitor/`에 있음 (저장소에는 없음): `check.sh`(점검), `backup.sh`(백업), `rollback.sh`(롤백), `user_rows.sh`(한 사용자의 표별 행 수), `set_admins.sh`(관리자 목록 정하기: 가입돼 있고 활성인 계정만 넣고, 기본은 미리보기).
- AWS 비용은 크레딧으로 나가며 하루 약 1달러(10/12 기준 거친 값). 프로젝트가 끝나면 서버를 중지하거나 삭제할 것(중지해도 디스크와 고정 IP 요금은 남음).

## 14. 남은 일

- 서버 전체 다운을 알려주는 외부 점검(예: GitHub Actions 주기 점검) 추가.
- **main 보호 규칙은 팀 결정으로 켜지 않음**(2026-10-13). main에 직접 push하면 리뷰 없이 바로 서버에 배포될 수 있고 강제 push도 막혀 있지 않음 → PR과 리뷰 관행을 유지하고, 사고가 나면 §6 롤백으로 대응. 쓰기 권한자 4명이 모두 admin이라, 필요하면 일부를 write로 내리는 것도 팀과 상의.
- 지인 체험이 끝난 뒤의 **삭제 순서**(날짜는 팀이 정함): (1) 혜림님 스크립트로 테스트 계정 삭제(미리보기 확인 뒤 `--apply`) → (2) 삭제 **뒤** 상태로 새 백업(`backup.sh`) → (3) 삭제 전에 만든 서버 백업 파일을 모두 지움 → (4) AWS 디스크 스냅샷 삭제 → (5) 맥북의 암호화 사본 삭제 → (6) 행 수와 남은 백업 목록 확인. 서버 백업을 지우는 스크립트는 아직 없음.
- 마이그레이션 사고 때 DB를 되돌리는 절차(`alembic downgrade` 또는 백업 복구)는 연습한 적이 없음.
- 서버 밖 자동 백업(S3 등)은 아직 없음.
- Docker 로그 크기 제한(`logging` 설정)이 없음. 지금은 크기가 작아서 급하지 않음.
- 공개 API에 요청 속도 제한이 없음(학생 체험 수준에서는 위험이 낮다고 보고 알고만 있음).
- 정식 예측 흐름(`/v1/predictions/jobs`), 20명 이상의 동시 접속, 몇 시간 이상의 장시간 부하는 시험하지 않음.

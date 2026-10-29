# 배포 인프라 노트 (작성: 효민 · 최초 2026-09-30 · 갱신 2026-10-14)

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
| OS | Ubuntu 26.04 LTS (2026-10-08 보안 업데이트와 재부팅, 2026-10-17 보안 업데이트, §11) |
| 루트 디스크 | 20GB gp3(파일시스템 19GB), **암호화됨**(2026-10-17, 키 `aws/ebs`), 볼륨 이름 `paeon-root-encrypted`, 가용 영역 `ap-northeast-2c` |
| 종료 시 삭제 | **아니요**(디스크를 손으로 바꿔 붙여서). 서버(인스턴스)를 삭제해도 이 볼륨은 남아 요금이 나오므로, 프로젝트가 끝나 서버를 없앨 때 볼륨도 직접 삭제할 것 |
| EBS 기본 암호화 | 켜짐(2026-10-17, 서울 리전). 앞으로 만드는 볼륨·스냅샷 사본은 자동 암호화 |
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

- compose 파일은 3306, 8000을 **서버 안(127.0.0.1)에만** 연결함(2026-10-17부터). 보안 그룹이 실수로 열려도 밖에서는 닿지 않는 두 번째 겹. 그래도 **보안 그룹 규칙은 다시 열지 말 것**. 열어야 할 이유가 생기면 팀에 먼저 알리기.
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
- **운영 API 문서는 밖에서 막혀 있음(2026-10-29)**: `/docs`, `/openapi.json`은 `@api` 목록에서 빼서 바깥에서는 404(경로와 요청 모양 전체가 공격 지도가 되지 않게, API 보안 검사). 운영 서버의 문서가 필요하면 맥북에서 SSH 터널을 열고 `http://localhost:8000/docs`로 봄: `ssh -N -L 8000:127.0.0.1:8000 paeon`(끝낼 때 Ctrl+C). 앱 포트는 서버 안쪽(127.0.0.1:8000)에만 열려 있어 터널로만 닿음. 로컬 개발 서버의 문서는 그대로.
- 화면과 API가 같은 주소(같은 출처)라서 CORS 설정이 필요 없음.
- `frontend/`의 변경은 main에 머지되면 화면에 자동 반영됨. 안 바뀌어 보이면 강력 새로고침(Cmd+Shift+R).
- **`Caddyfile`이 바뀐 PR은 머지 뒤 Caddy를 직접 다시 시작해야 반영됨.** 배포는 서버의 파일만 바꾸고, 떠 있는 Caddy 컨테이너는 처음 시작할 때 읽은 파일을 계속 붙잡고 있음(2026-10-21: #151 머지 뒤에도 3MB 요청이 422로 앱까지 가서 발견). 순서(서버):
  ```bash
  cd ~/AH_06_03 && git log --oneline -1
  sudo docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | tail -1
  sudo docker compose restart caddy; echo "restart exit=$?"
  sudo docker compose ps caddy --format "table {{.Service}}\t{{.Status}}"
  ```
  `docker compose exec caddy caddy validate`는 **예전 파일**을 검사하므로, 새 파일은 위처럼 임시 컨테이너로 검사함. 재시작 뒤 상태가 `Up 몇 초`인지 확인(그대로 `Up 3 days` 등이면 재시작이 안 된 것).
- 요청 본문 크기 제한 **2MB**(#151, `request_body`): 넘으면 앱에 닿기 전에 413. 확인(맥북): `head -c 3000000 /dev/zero > /tmp/big.bin && curl -s -o /dev/null -w "%{http_code}\n" --data-binary @/tmp/big.bin https://54-116-113-17.sslip.io/v1/auth/login` → `413`.
- 화면 파일(`/`, `*.html`, `*.js`, `*.css`)은 `Cache-Control: no-cache`(#157): 쓸 때마다 바뀌었는지 확인하고, 안 바뀌었으면 304. 배포 직후 브라우저가 예전 파일을 써서 화면이 깨지는 일을 막음. 글꼴·이미지는 그대로 캐시.
- 화면이 아닌 앱(Capacitor) 프로젝트 파일(`/android/*`, `/ios/*`, `package.json`, `package-lock.json`, `capacitor.config.json`)은 404(#157).

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

### 데이터를 바꾸는 PR의 배포 순서 (2026-10-21, #145에서 정함)

- 서버에 영향이 있는 PR은 제목에 **`[배포 영향]`**을 붙이고, 머지 전에 배포 담당에게 알림. 마이그레이션 PR은 머지 직전에 마이그레이션 머리가 하나인지 확인(§9).
- **DB 구조 변경은 2026-10-24에 동결**(체험 데이터 보호), 기능 변경은 10/27에 동결(팀 합의 10/19).
- 새 키가 필요한 PR(예: 이메일 암호화): ① 서버 `.env`에 키를 먼저 넣음(값은 화면에 띄우지 않고 생성) → ② 키체인·비밀번호 관리자에 사본, 지문 비교로 확인 → ③ `backup.sh` → ④ 머지·배포 → ⑤ 서버에서 확인(마이그레이션 번호, 에러 0, 데이터 검증) → ⑥ 브라우저 확인. 키 없이 머지되면 새 코드가 먼저 떠서 로그인이 멈춤.
- 명령은 **어느 터미널(서버/맥북)인지** 적고, "확인 → 실행"이 필요한 명령은 나눠서 실행. 긴 스크립트는 붙여 넣다 잘릴 수 있으니 파일로 만들어 `scp`로 보냄(2026-10-21 겪음). 컨테이너 안에서 파일로 실행할 때는 `sudo docker compose exec -T fastapi sh -c 'python - < /tmp/파일.py'`(그냥 `python /tmp/파일.py`는 `app`을 못 찾음).
- 커밋 전에 `git branch --show-current`로 main이 아닌지 확인(2026-10-21 커밋이 로컬 main에 만들어진 일이 있었음, push 전에 바로잡음).

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
- **백업(서버 7일치, 맥북 사본)과 스냅샷에는 탈퇴 전 데이터가 남음.** 탈퇴 시 백업에서도 지워야 하는지는 정책으로 정할 것(§14).

### 관리자 행위 기록 (`admin_audit_logs`)

- 관리자 화면의 변경(미션·카테고리의 노출과 순서)과 열람(목록·통계·기록)을 시각과 함께 남기는 표. 마이그레이션 `c5a1d7e3b902`(PR #74)로 만들어졌고, 서버에서 적용과 색인 3종을 확인함(2026-10-13).
- 칸: `actor_email`(관리자 이메일), `action`, `target`, `detail`, `created_at`(UTC). **`user_id` 칸을 일부러 두지 않음**: 회원 탈퇴가 `user_id` 칸이 있는 표를 지우고 내 데이터 내려받기가 그 표들을 담기 때문에, 관리자가 탈퇴해도 기록이 남아야 함. 사용자 개인정보는 담지 않음.
- 열람 기록은 같은 관리자·같은 동작이면 10분 안에 한 번만 남김. 거절된 변경이나 값이 같은 변경은 남기지 않음.
- 동작별 개수 보기(읽기만 하고 이메일은 안 나옴). **SQL의 별칭에 한글을 쓰지 말 것**: 서버에서 한글이 깨져 문법 오류가 남.

```bash
grep '^DB_ROOT_PASSWORD=' .env | cut -d= -f2- | sudo docker compose exec -T mysql sh -c 'IFS= read -r p; export MYSQL_PWD="$p"; mysql -uroot paeon -e "SELECT action, COUNT(*) AS n FROM admin_audit_logs GROUP BY action ORDER BY action;"'
```

- **보관 기간은 2년**: 서버가 새 기록을 남길 때 2년(730일)이 지난 기록을 자동으로 지움(`audit_service.py`). 체험이 끝났다고 비우지 않음. 민감정보(건강정보)를 처리하는 시스템 기준(2년 이상)을 따라 팀이 2년으로 통일함(처리방침과 같음, 2026-10-20).
- **관리자 권한 부여·회수** 기록(`admin_granted`, `admin_revoked`): 서버가 켜질 때 `ADMIN_EMAILS`를 지난 기록과 비교해 `system(서버 설정)`이 한 일로 남김. 누가 바꿨는지는 모르고 반영된 시점만 남음. 처음 켜질 때 현재 관리자 4명이 `admin_granted`로 기록됨(2026-10-14 서버에서 확인).
- **권한 부여·회수 기록(`admin_granted`, `admin_revoked`)은 3년(1095일) 보관**: 안전성 확보조치 기준이 개인정보취급자의 접근 권한 부여·변경·말소 내역을 최소 3년 보관하라고 함(2026-10-20 멘토링·팀 점검). 나머지 행위 기록은 2년. 둘 다 새 기록을 남길 때 자동으로 지움(`audit_service.py`의 `RETENTION_DAYS`, `GRANT_RETENTION_DAYS`).

### 서비스 접속 기록 (`access_logs`)

- 로그인에 성공하면 `account_id`, 시각, IP를 남김. **3개월(93일)** 보관하고, 오래된 기록은 다음 로그인 때 함께 지움. `user_id` 칸이 없어서 **탈퇴해도 남음**(탈퇴 삭제와 내려받기 대상이 아님).
- IP는 `X-Forwarded-For`의 첫 값을 씀. Caddy가 바깥에서 온 값을 덮어쓰므로 실제 방문자 IP가 기록되는 것을 2026-10-14 배포 뒤 서버에서 확인함(Docker 내부 주소가 아닌 공개 IP). **이 값이 틀리면 비회원 문의의 IP별 접수 제한이 모든 사용자에게 한꺼번에 걸림.** 배포 뒤에는 로그인을 한 번 하고 아래를 맥북의 공개 IP(`curl -s https://ifconfig.me`)와 비교함(IP는 채팅이나 문서에 붙이지 말 것).

```bash
grep '^DB_ROOT_PASSWORD=' .env | cut -d= -f2- | sudo docker compose exec -T mysql sh -c 'IFS= read -r p; export MYSQL_PWD="$p"; mysql -uroot paeon -e "SELECT ip, created_at FROM access_logs ORDER BY created_at DESC LIMIT 1;"'
```

### 이메일 암호화 (`users.email_enc`, `users.email_hash`, 2026-10-21 배포)

- #145: 이메일을 `email_enc`(Fernet으로 잠근 값)와 `email_hash`(찾기용 지문, HMAC-SHA256)로 저장. 코드에서는 `user.email`로 읽고 쓰면 두 칸이 같이 채워지고, 쿼리의 `User.email == x`는 지문 비교로 바뀜. 일부 글자 검색·정렬은 안 됨(바로 오류).
- 키: 서버 `.env`의 `PII_ENC_KEY`(잃으면 이메일을 못 엶), `PII_HASH_KEY`(잃으면 **아무도 로그인 못 함**). 맥 키체인 `PAEON_PII_ENC_KEY`·`PAEON_PII_HASH_KEY`와 비밀번호 관리자에 사본. 서버와 키체인이 같은지는 지문 앞 8글자로 비교(값은 화면에 안 나옴):
  ```bash
  for k in PII_ENC_KEY PII_HASH_KEY; do echo "$k 서버 $(ssh paeon "grep '^$k=' ~/AH_06_03/.env | cut -d= -f2- | tr -d '\n' | sha256sum | cut -c1-8") / 키체인 $(security find-generic-password -a "$USER" -s PAEON_$k -w | tr -d '\n' | shasum -a 256 | cut -c1-8)"; done
  ```
- 관리자 화면은 가린 이메일만 보이고, 회원 상세의 "이메일 보기"를 누를 때만 전체를 보여 주며 관리자 기록에 `user_email_view`로 남음. 가입자 검색은 **이메일 전체** 또는 회원 번호 일부로만.
- 배포 뒤 확인(2026-10-21): 회원 20명 전원이 풀리고 다시 만든 지문이 저장된 지문과 같음, 평문 0. 머지 전 백업(`paeon-20261021-0113`)과 회원별로 비교해 20명 모두 이메일이 같음.
- 옛 평문 칸 `users.email`은 비어 있고, 칸 자체는 2단계(#158, 마이그레이션 `1a9a51da1d1a`)에서 지움. 평문이 남아 있으면 그 마이그레이션은 지우지 않고 멈춤.
- 관리자 기록의 관리자 이메일(`actor_email`), `.env`의 `ADMIN_EMAILS`, 생년월일·건강 수치·설문 답은 이번 범위가 아님(멘토링 10/20: 필수는 이메일까지, 건강정보는 여유가 있으면).

### 문의 (`inquiries`, `guest_inquiries`)

- **1:1 문의**(`inquiries`): 로그인한 이용자가 남기고 관리자가 답함. `user_id` 칸이 있어서 **탈퇴하면 같이 삭제**되고 건강정보 동의 철회로는 안 지움. 답 없는 문의는 1인당 5개까지. 관리자가 열면 행위 기록에 문의 번호만 남고 내용은 남기지 않음.
- **비회원 문의**(`guest_inquiries`): 로그인 없이 남김(로그인·가입이 안 될 때). IP와 조회 번호는 **해시만 저장**함(서버 비밀값 `JWT_SECRET`으로 섞어서 해시하므로, `JWT_SECRET`을 바꾸면 기존 조회 번호로는 답변을 못 봄). 스팸 방지: IP별 1시간 3번·하루 10번, 숨은 칸(허니팟), 링크 2개 제한, 답 없는 문의가 300개가 되면 접수 중단. 접수 후 **30일**이 지나면 삭제.

### 서비스 안 공지 (`notices`)

- 이용약관의 "약관 변경·서비스 종료는 서비스 안에서 공지"를 지키기 위한 표(마이그레이션 `f7a3d1c9e582`). 칸: 제목, 내용, 시작·종료 시각(UTC), 쓴 관리자 이메일. 공지 내용은 모두에게 공개되는 글이라 사용자 정보를 담지 않음.
- 이용자용 `GET /v1/notices`: 로그인 없이, **지금 게시 중인 공지만** 최신순 10개. 쓴 관리자 정보는 내려주지 않음. 배너 표시는 이슬님이 UI 개편 때 넣음(내용은 글자 그대로라 HTML로 해석하지 않고 글자로만 보여 줘야 함).
- 관리자용 `GET`/`POST /v1/admin/notices`(목록, 작성)와 `PATCH /v1/admin/notices/{id}`(수정, `{"end_now": true}`로 바로 내리기). **삭제 기능은 없고** 종료 시각으로 내려서 이력을 남김.
- **관리자 화면의 "공지" 탭**(#168, 2026-10-22): 제목·내용·시작·끝을 넣어 올리고, 목록에서 수정하거나 "지금 내리기". 시각은 **한국 시각으로 입력**하면 화면이 `+09:00`을 붙여 보내고 서버가 UTC로 저장함. 이용자 화면에서는 홈 팝업, 종 알림, 더보기의 공지사항에 보임(이슬님 10/16). 이제 Swagger로 올릴 필요 없음.
- 작성할 때 `starts_at`, `ends_at`은 **비워도 됨**(비우면 시작은 지금, 끝은 없음). 둘 다 넣으면 끝이 시작보다 뒤여야 함(같거나 앞이면 422).
- 작성·수정은 관리자 행위 기록(`notice_create`, `notice_update`)에 제목만 남기고 내용은 남기지 않음.
- 2026-10-14 서버에서 만들기, 이용자 목록에 보이기, 내리기(`ended`)까지 확인함. 시험은 `https://54-116-113-17.sslip.io/docs`(Swagger)에서 함(아래 §9의 주의사항 참고).

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
- 결과: `~/backups/paeon-날짜-시각.sql.gz`(파일 이름과 시각은 UTC), 권한 600, 폴더 700.
- 보관: **7일이 지난 백업은 지움**(`KEEP_DAYS=7`). 손으로 뜬 백업이 끼어도 매일 백업 7일치가 그대로 남고, 처리방침의 "삭제 후 백업에는 최대 일주일"과 맞음. 단, **가장 최근 백업 1개는 날짜와 상관없이 남김**(백업이 며칠 연속 실패해도 되돌릴 곳이 하나는 있게).
- 2026-10-15에 "최근 7개"에서 바꿈. 예전 기준은 머지 전에 손으로 뜬 백업이 끼면서 실제로는 **매일 백업 사흘치**만 남아 있었음.
- 덤프가 끝까지 만들어졌는지 검사하고, 실패하면 디스코드로 알림. 실패한 날에는 파일이 안 생김.
- 백업이 **36시간 넘게 안 갱신되면** 점검 스크립트가 경고함(§10).
- 수동으로 지금 한 번 뜨기: `bash ~/paeon-monitor/backup.sh` (마이그레이션 PR을 머지하기 전에 권장).
- **마이그레이션 전에 뜬 백업은 최신 구조가 아님.** 복원하면 `alembic_version`도 그때 값으로 돌아가므로, 복구할 때는 코드와 DB 구조가 맞는지 확인해야 함(시험으로 확인한 사실, 2026-10-08).
- 커뮤니티 사진(JPEG)이 백업에 **원래 바이트 그대로** 들어 있음. 백업을 글자로 읽는 스크립트는 `errors="replace"`로 열어야 함(2026-10-21 겪음). 사진이 든 백업의 복원 시험은 **2026-10-21 통과**: 임시 MySQL에 3초 만에 복원, 표 49개의 행 수와 사진 바이트 지문, 암호화된 이메일 지문, 마이그레이션 번호가 운영 DB와 모두 같았음. 같은 시험을 다시 하려면 서버의 `bash ~/restore_check.sh`(새 백업 → 임시 복원 → 비교 → 임시 컨테이너·볼륨 삭제, 값은 출력 안 함).

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

- 효민의 맥북 `~/paeon-backups/`에 암호화한 사본을 둠(AES-256, openssl). 암호는 맥 키체인 항목 `PAEON_BACKUP_PASS`와 비밀번호 관리자에 있고 값은 문서에 없음. 주기적인 자동 반출은 없음(S3는 하지 않기로 함).
- 만들기와 확인(맥북, 암호는 키체인에서 바로 넘겨서 화면에 안 나옴):
  ```bash
  f=$(ssh paeon 'ls -1t ~/backups/paeon-*.sql.gz | head -1'); echo "$f"
  P="$(security find-generic-password -a "$USER" -s PAEON_BACKUP_PASS -w | tr -d '\n')" sh -c 'ssh paeon "cat $0" | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:P -out ~/paeon-backups/$(basename "$0").enc' "$f"
  P="$(security find-generic-password -a "$USER" -s PAEON_BACKUP_PASS -w | tr -d '\n')" openssl enc -d -aes-256-cbc -pbkdf2 -pass env:P -in ~/paeon-backups/$(basename "$f").enc | gzip -dc | tail -1
  ```
  마지막 줄이 `-- Dump completed on ...`이면 암호와 파일이 모두 정상. 일주일이 지난 맥북 사본은 지움(2026-10-17에 새로 만들고 10/11 사본 삭제).
- 백업 파일에는 **사용자가 입력한 건강정보가 들어 있음.** 채팅, 깃허브, 디스코드에 올리지 말 것.

### 서버 로그 보관

- 컨테이너 로그는 서비스마다 **10MB x 5개**까지만 남음(`docker-compose.yml`의 `x-logging`). 넘치면 오래된 줄부터 지워짐.
- 보관용 사본: 서버의 `~/paeon-monitor/log_archive.sh`(저장소에는 없음)가 cron으로 **매시 7분**에 fastapi, caddy, mysql 로그를 `~/logs/연-월/서비스-날짜.log.gz`로 옮김(한국 날짜 기준, 파일 600, 폴더 700). **배포 직전에도 한 번** 실행됨(`deploy.yml`). 컨테이너를 다시 만들면 그 컨테이너의 로그가 사라지기 때문.
- 보관 기간: 스크립트 맨 위 `RETENTION_DAYS`(**93일**, 2026-10-20). 멘토님이 "1년·5년을 따지지 말고 기록 종류별로 나눠 지우는 로직을 갖추면 된다"고 정리해 주셔서, 서버 로그는 이용자 접속 기록과 같은 3개월로 맞춤. 처리방침의 서버 로그 보관 기간과 같게 유지할 것.
- 기록 종류별 보관(정리): 이용자 접속 기록 `access_logs` 3개월(DB, 자동 삭제), 서버 로그 3개월(`log_archive.sh`), 관리자 행위 기록 2년(DB, 자동 삭제), 권한 부여·회수 기록 3년(DB, 자동 삭제, §7), 백업 7일(§8).
- 어디까지 옮겼는지는 `~/logs/.last_until`(UTC 시각)에 적힘. 읽기에 실패하면 위치를 앞으로 옮기지 않아 다음 실행이 같은 구간을 다시 가져감(이때 일부 줄이 두 번 들어갈 수 있음). 실패는 `~/logs/errors.log`에 남음.
- 보기: `zcat ~/logs/2026-10/fastapi-2026-10-17.log.gz | less`
- `rollback.sh`도 컨테이너를 다시 만들므로, 시간 여유가 있으면 롤백 전에 `~/paeon-monitor/log_archive.sh`를 한 번 돌림.

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

### Swagger(`/docs`)로 API를 시험할 때 자주 걸리는 것 (2026-10-14 공지 시험에서 겪음)

- **401 `AUTH_TOKEN_EXPIRED`**: 접근 토큰은 30분만 유효함. `POST /v1/auth/login`을 다시 하고 응답의 `access_token` 값만(따옴표 없이, 앞에 `Bearer ` 없이) 위쪽 **Authorize**에 넣음.
- **422(끝나는 시각은 시작하는 시각보다 뒤여야 함)**: Swagger가 Request body 예시에 `starts_at`과 `ends_at`을 **같은 시각으로 채워 줌**. 비워도 되는 칸은 줄째로 지우고 보냄.
- **404(찾을 수 없음)**: 응답의 번호(`notice_id` 등)를 복사할 때 **양쪽 따옴표까지** 붙여 넣으면 주소 끝에 `%22`가 붙어서 생김. 값을 더블클릭해 따옴표 없이 복사함.
- **스크린샷이나 채팅에 올릴 때**: curl 칸의 `Authorization: Bearer ...` 줄에 로그인 토큰이 통째로 보이므로 그 줄을 가리고 올림. 시험이 끝나면 Authorize에서 Logout함.

### 배포의 `alembic upgrade head`가 `Multiple head revisions are present`로 실패

- 원인: 마이그레이션이 든 PR이 둘 이상인데 같은 번호 뒤에 붙어서 마이그레이션 머리가 둘이 됨. 2026-10-13에 혜림님 동의 v4 PR과 관리자 행위 기록 PR이 같은 번호 뒤에 있어서 머지 전에 발견하고 머지 순서를 정함.
- 예방: 마이그레이션이 든 PR이 동시에 있으면 머지 순서를 정하고, 뒤 PR의 `down_revision`을 앞 PR의 마지막 번호로 맞춘 뒤 머지함. 저장소 폴더에서 머리가 하나인지 세어 봄:

```bash
python3 - << 'EOF'
import glob, re
revs, downs = {}, set()
for f in glob.glob('alembic/versions/*.py'):
    t = open(f, encoding='utf-8').read()
    r = re.search(r"^revision(?:: str)?\s*=\s*['\"]([0-9a-f]+)['\"]", t, re.M)
    d = re.search(r"^down_revision(?:[^=]*)=\s*['\"]([0-9a-f]+)['\"]", t, re.M)
    revs[r.group(1)] = f
    if d: downs.add(d.group(1))
print([r for r in revs if r not in downs], "<- 하나여야 함")
EOF
```

- 이미 머지돼서 깨졌다면: `alembic merge -m "merge heads" 번호1 번호2`로 두 머리를 합치는 마이그레이션을 만들어 새 PR로 올림(작은 환경에서 합친 뒤 머리가 하나가 되고 `upgrade head`가 도는 것을 확인함). Revert는 하지 말 것(§6).
- 확인 팁: 파이썬은 같은 크기로 바꾼 파일을 같은 초 안에 다시 읽으면 옛 캐시를 쓸 수 있으니, 번호를 고친 뒤 머리를 셀 때는 `__pycache__`를 지우고 셀 것.

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

### 이미 쓰던 DB에 옛 브랜치를 올리면 500 (`Unknown column 'users.email'`, 2026-10-22 테스트 서버)
- 증상: 로그인·문의 목록·4주 재입력 화면이 500. 로그에 `1054 Unknown column 'users.email'`, alembic은 `Can't locate revision identified by '1a9a51da1d1a'`.
- 원인: DB는 #159(옛 평문 `users.email` 칸 삭제)까지 올라갔는데, #159 전에 갈라진 브랜치 코드를 올려서 코드가 없는 칸을 찾음. 자동 시험은 매번 새 DB를 만들어 잡지 못함.
- 조치: 브랜치에 최신 main을 합치고 테스트 DB를 새로 만듦(`down -v`는 테스트 서버에서만). `alembic stamp`로 번호만 바꾸는 건 구조가 그대로라 쓰지 않음.
- 예방: 쓰던 DB에서 브랜치를 바꾸기 전에 `alembic current`(DB)와 `alembic heads`(코드)를 비교. `current`가 `Can't locate revision`이면 코드가 뒤처진 것이니 main부터 합침.
- 자세한 기록: `docs/트러블슈팅_테스트서버_마이그레이션_1022.md`

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

### 운영 알림 (앱이 관리자에게 보내는 디스코드 알림)

- 서버 점검 알림과 별개로, **앱이** 관리자가 빨리 봐야 하는 일을 디스코드 #관리자-알림으로 보냄(`app/services/admin_alert.py`).
  - 신고 3명 누적으로 글·댓글이 자동 숨김될 때: "🔒 커뮤니티 글 1건이 신고 3명으로 자동 숨김됐어요…"
  - 새 1:1 문의·비회원 문의가 실제로 접수될 때: "💬 새 1:1 문의가 1건 들어왔어요…" (봇·횟수 제한으로 막힌 문의는 알리지 않음)
- 글 내용, 작성자, 번호는 보내지 않음(디스코드는 서비스 밖). 백그라운드로 보내서 요청을 늦추지 않고, 실패해도 요청은 정상 처리되며 로그에 주소를 남기지 않음.
- 주소는 서버 `.env`의 `ADMIN_ALERT_WEBHOOK`(점검 알림의 `~/.monitor.env`와 다름). 비우면 알림만 꺼짐. 바꿀 때는 `nano .env`로 고친 뒤(`echo`로 넣지 말 것) `sudo docker compose up -d --force-recreate fastapi`.
- 시험 메시지: `sudo docker compose exec -T fastapi python -c "import asyncio; from app.services import admin_alert; asyncio.run(admin_alert._post('✅ PAEON 운영 알림 시험'))"`

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
- 2026-10-17 점검 때: `sudo apt update` → `sudo NEEDRESTART_MODE=a apt upgrade -y`로 10개 업데이트(docker 29.8.2 → 29.9.1, containerd 2.3.6 → 2.4.2 포함). 재부팅 필요 없었고, 컨테이너는 내려가지 않고 그대로 떠 있었음.

### 디스크 암호화 (2026-10-17 완료)

- 순서: 기준 숫자 기록 → `backup.sh`와 맥북 사본 → 서버 중지 → 루트 볼륨 스냅샷 → 그 스냅샷으로 "이 볼륨 암호화"를 켠 새 볼륨 생성 → 옛 볼륨 분리 → 새 볼륨을 `/dev/sda1`로 연결 → 서버 시작 → 기준 숫자 비교. 실제 절차는 체크리스트 문서에 있음.
- 결과: 상태 검사 3/3 통과, 컨테이너는 부팅과 함께 자동 시작, 코드·계정 수(활성 10, 탈퇴 8)·마이그레이션 번호·디스크 사용량이 작업 전과 같음. SSH 경고 없음.
- 겪은 것과 주의할 것:
  - 스냅샷에서 볼륨을 만들 때 **가용 영역 기본값이 `ap-northeast-2a`**였는데 서버는 `ap-northeast-2c`. 다르면 붙일 수 없으니 반드시 서버와 같게 맞출 것.
  - 서버 안에서는 디스크가 `nvme0n1`으로 보이지만, 콘솔에서 붙일 때는 **루트 디바이스 이름 `/dev/sda1`**을 씀.
  - 옛 볼륨 분리가 끝나기 전에는 `/dev/sda1`이 "이미 사용 중"으로 나옴. 옛 볼륨이 "사용 가능"이 된 뒤 붙임.
  - 새 볼륨이 "초기화 중(n%)"이어도 "사용 가능"이면 바로 쓸 수 있음(데이터를 뒤에서 옮기는 중이라 첫 부팅만 조금 느림).
  - 태그 키는 대문자 `Name`이어야 콘솔 목록의 이름 칸에 보임.
- 남은 정리는 §14.

## 12. 보안 약속

- 밖에 열린 문은 **22, 80, 443**만. 규칙을 추가하기 전에 팀에 알리기. DB 포트는 열지 않고, DB 확인은 SSH로.
- 키, `.env` 값, 웹훅 주소, 토큰, 백업 파일은 채팅·깃허브·디스코드에 붙여넣지 않음. **노출되면 지체 없이 폐기하고 새로 만듦.**
- `GUARDIAN_ENC_KEY`와 백업 암호는 잃어버리면 보호자 정보와 백업을 못 여니, 서버 밖에 별도로 보관해 둠(담당: 효민, 맥 키체인과 비밀번호 관리자에 사본, 해시 지문 비교로 일치 확인). 값은 문서에 적지 않음.
- 서버에서 직접 고친 설정은 저장소에 반영(커밋)할 것. `main`에는 직접 push하지 않고 PR로 합치기로 함. GitHub의 main 보호 규칙은 켜지 않기로 했고(팀 결정, 2026-10-13), PR과 리뷰 관행으로 지킴. 직접 push가 기술적으로 막혀 있지는 않아서, 서버가 깨지면 §6의 롤백으로 복구함.
- 사용자(지인) 입력값은 건강정보이므로, DB를 확인할 때 값 대신 개수만 보고 필요한 사람만 접근함.
- **로그인 시도 제한**(2026-10-16): 같은 이메일로 15분 안에 5번 틀리면 잠시 막고(성공하면 초기화), 같은 IP에서 15분 안에 `LOGIN_MAX_FAILS_PER_IP`(기본 50)번 틀리면 그 IP를 막음. 실패 횟수는 앱 메모리에만 있어 재배포하면 0으로 돌아가고, "로그인 실패는 접속 기록을 남기지 않는다"는 팀 결정을 지킴. 체험 안내처럼 여러 명이 같은 와이파이로 로그인하는 날에는 `.env`에서 늘림. uvicorn을 여러 프로세스로 늘리면 DB나 Redis로 옮겨야 함.
- **한 계정 한 기기**(2026-10-15): 새로 로그인하면 다른 기기의 로그인이 바로 끊김. 이용 정지도 즉시 모든 기기에서 로그아웃.
- **보안 헤더**(2026-10-16, `Caddyfile`): HSTS, iframe 차단(`X-Frame-Options`, CSP `frame-ancestors`), `nosniff`, Referrer-Policy, 카메라·마이크·위치 권한 차단, Server 헤더 제거. **Caddyfile만 바뀐 배포는 자동 반영이 안 되므로** 머지 뒤 `sudo docker compose restart caddy`(2~3초 끊김). 확인(맥북): `curl -sI https://54-116-113-17.sslip.io/ | grep -iE "strict-transport|x-frame|x-content-type|^server"`
- **비밀값 노출 기록**: 2026-10-15 채팅 캡처로 서버 `.env` 일부가 보임 → `JWT_SECRET`은 즉시 교체(재발급 토큰은 DB 값이라 사용자 영향 거의 없음). `DB_PASSWORD`·`DB_ROOT_PASSWORD`·`GUARDIAN_ENC_KEY`는 일부만 보였고 밖에서 3306이 닫혀 있어 교체 보류(멘토링에서 확인). 2026-10-16 디스코드 웹후크 주소가 채팅에 노출 → 디스코드에서 삭제. **`.env` 화면과 웹후크 주소는 캡처·붙여넣기 하지 않기.**
- **API 보안 검사**(멘토링 10/20 권장, 묶음별): 1묶음(가입·로그인·계정) → 탈퇴 비밀번호 시도 제한·재발급 상태 확인(#147), 서명 키 기본값이면 서버가 안 켜짐(#152, 재시작 전 `grep -c '^JWT_SECRET=[0-9a-f]\{64\}$' .env`가 1인지 확인). 2묶음(건강정보·예측) 큰 문제 없음. 4묶음(커뮤니티·파티) → 요청 크기 2MB·사진은 300KB 넘는 순간 읽기 중단·파티 초대 코드 1시간 10번 틀리면 막기(#151). 멘토님 지적 → 공통 챌린지에도 건강정보 동의 확인(#149). 남은 묶음: 챌린지, 공통 챌린지, 문의·공지·캘린더, 관리자.
- **API 보안 검사 마무리(2026-10-27)**: 관리자 경로 35개를 실제로 호출해 로그인 없이 401·일반 회원 403 확인, 관리자 계정은 정지·삭제·일괄 삭제 대상에서 빠짐, 바꾸는 동작과 개인정보 열람은 모두 관리자 기록에 남음(공지 목록 보기만 기록 없음, 개인정보 없음). 회원용 106개 중 로그인 없이 열리는 곳은 의도한 7개(로그인, 가입, 재발급, 약관, 비회원 문의 쓰기·조회, 공지)뿐. 두 계정으로 남의 문의·캘린더 할 일·댓글·챌린지 사이클을 읽고 바꾸는 시도는 모두 404. 인기도·좋아요·감사 파이·아이템 구매는 중복 없음. 고친 것: **로그아웃해도 그 기기로 이전 사람의 알림이 계속 오던 문제**(로그아웃 때 이 기기의 푸시 구독을 서버와 브라우저에서 지움).
- **서명 키(`JWT_SECRET`)를 바꾸면 비회원 문의 조회 번호도 무효가 됨**: 비회원 문의는 조회 번호와 IP를 이 키로 섞은 해시로 저장해서, 키를 바꾸면 그 전에 받은 번호로는 문의를 찾을 수 없고 IP별 접수 제한 기록도 초기화됨. 비회원 문의는 30일 뒤 지워져 영향은 작지만, 키를 바꿀 때는 이 점을 알리고 바꿈(10/14~10/15에 받은 번호는 10/15 키 교체로 이미 조회 불가일 수 있음).
- **저장소는 공개(Public)**: 코드, 문서, PR, Actions 로그를 누구나 볼 수 있음. 비밀값, 실제 사용자 데이터, 서버 접속 키는 올리지 않음. 2026-10-13에 전체 기록(커밋 243개, 브랜치 20개)을 훑어 개인 키, AWS 키, 웹훅 주소, 토큰 모양과 `.env` 파일이 없음을 확인함(`.env.example`의 값은 `change-me`뿐). 검사 범위는 1MB 미만 파일과 위 패턴이라 완전한 보증은 아님.
- **저장소 권한**: 직접 접근 권한자 4명(모두 admin, 1명은 외부 협업자). 쓰기 권한이 있으면 배포 워크플로를 통해 서버에 명령을 실행할 수 있어서, 이 4명이 "서버를 관리하거나 서비스를 올릴 수 있는 사람"임(개인정보 방침의 N=4). 서버에 직접 접속하는 SSH 키를 가진 사람은 1명이고, 비밀번호 접속은 막혀 있음(`passwordauthentication no`, 2026-10-13 확인).

## 13. 알아두면 좋은 것

- GitHub Secrets: `EC2_HOST`(=54.116.113.17), `EC2_SSH_KEY`(서버 접속 키), `DISCORD_WEBHOOK`(배포 알림용).
- 서버 `.env` 항목(값은 문서에 없음): `DB_HOST`·`DB_PORT`·`DB_NAME`·`DB_USER`(설정), `DB_PASSWORD`·`DB_ROOT_PASSWORD`(비밀번호, 서버에서 다시 정할 수 있음), `JWT_SECRET`(로그인 토큰 서명 키, 바꾸면 전원 한 번 재로그인), `GUARDIAN_ENC_KEY`(보호자 정보 암호화 키, **잃으면 복구 불가**, 키체인 `PAEON_GUARDIAN_ENC_KEY`와 비밀번호 관리자에 사본), `ADMIN_EMAILS`(관리자 목록), `ADMIN_ALERT_WEBHOOK`(운영 알림 주소, §10), `LOGIN_MAX_FAILS_PER_IP`(선택, 기본 50, §12). `.env` 전체 사본은 비밀번호 관리자의 보안 메모에 있음(키를 바꾸면 같이 갱신).
- `.env` 추가 항목(2026-10-21): `PII_ENC_KEY`·`PII_HASH_KEY`(이메일 암호화 키, §7), `DEMO_AUTOFILL=1`·`DEMO_AUTOFILL_FINAL_DAY=2026-10-25`(**지인 체험용**: 3일치 기록으로 4주를 채움. 체험이 끝나면(10/25 23:59 이후) 두 줄을 지우고 다시 만들 것: `sed -i '/^DEMO_AUTOFILL/d' .env && sudo docker compose up -d --force-recreate fastapi`). 설정은 모르는 이름을 무시하므로(`extra: ignore`) 코드보다 먼저 넣어도 서버가 켜짐.
- 체험 설정 이름 변경(2026-10-22): `DEMO_AUTOFILL_FINAL_DAY` → **`DEMO_AUTOFILL_END=2026-10-25`**(#165, 체험 마지막 날. 이 날은 기록이 1일뿐이어도 채움). 형식이 `YYYY-MM-DD`가 아니면 경고만 남기고 무시함. 서버 `.env`에는 `DEMO_AUTOFILL=1`, `DEMO_AUTOFILL_END=2026-10-25` 두 줄이 있고, 10/26에 끌 때 `sed -i '/^DEMO_AUTOFILL/d' .env`가 두 줄을 같이 지움.
- **동시 접속 한계(추정, 2026-10-22)**: 앱 프로세스 1개, DB 연결은 기본값으로 동시 15개(자리가 날 때까지 최대 30초 대기 후 500), 로그인·가입은 초당 약 5.5건, 가벼운 API는 초당 약 126건(10/12 실측). 그래서 20명이 각자 쓰는 정도는 여유가 크고, 같은 순간에 로그인이 몰리면 오류보다 먼저 느려짐(20명이면 마지막 사람이 4초쯤 대기). 약 150명 이상이 같은 순간에 로그인해야 30초 대기를 넘겨 오류가 날 수 있음. 실제로 잰 것은 동시 10명까지이고, 정확한 한계는 체험 뒤 **테스트 서버에서**(운영 서버 말고) 부하 시험으로 잴 것.
- **`.env`를 바꾼 뒤에는 `restart`가 아니라 `sudo docker compose up -d --force-recreate fastapi`**(다시 만들어야 새 값을 읽음). 줄을 덧붙이기 전에 파일 끝 줄바꿈 확인: `[ -n "$(tail -c1 .env)" ] && echo >> .env`. 같은 줄이 두 번 들어가지 않았는지 `grep -n '^이름' .env`로 확인.
- 서버 변경은 가능하면 PR로 합의하고 한 PR로 묶어 머지 횟수를 줄이기.
- **관리자 화면**(`https://54-116-113-17.sslip.io/admin.html`, 메뉴에 링크 없이 주소로만): 챌린지 미션의 노출(켬/끔)과 카테고리 순서를 바꾸고, 챌린지 통계(미션별 선택 수·달성률·포기율, 4주 완료율)와 관리자 행위 기록(최근 50건)을 봄. 서버 `.env`의 `ADMIN_EMAILS`(쉼표로 구분한 이메일, 비면 아무도 못 씀)에 있는 계정이 평소 로그인으로 들어와서 씀. 목록을 바꾼 뒤에는 `sudo docker compose up -d --force-recreate fastapi`가 필요함(약 5초 끊김). **이메일 인증이 없어서 먼저 가입된 계정만 목록에 넣을 것**(가입 전 이메일을 넣으면 다른 사람이 먼저 가입해 관리자가 될 수 있음). 바꾼 내용은 서버 로그에 남음. 고정 미션(금연·절주)은 규칙이 정해서 스위치가 없음. 변경과 열람은 `admin_audit_logs`에 남음(§7).
- 서버에서 도는 도구는 `~/paeon-monitor/`에 있음 (저장소에는 없음): `check.sh`(점검), `backup.sh`(백업), `rollback.sh`(롤백), `user_rows.sh`(한 사용자의 표별 행 수), `set_admins.sh`(관리자 목록 정하기: 가입돼 있고 활성인 계정만 넣고, 기본은 미리보기), `log_archive.sh`(컨테이너 로그를 `~/logs`로 옮겨 보관, §8).
- 2026-10-21: `user_rows.sh`·`set_admins.sh`를 이메일 암호화에 맞게 고침(이메일 → 앱 컨테이너에서 찾기용 지문을 만들어 찾음, 이메일은 표준 입력으로만 넘김). `user_rows.sh`는 `user_id` 칸이 있는 표를 DB에서 자동으로 찾아 전부 셈(34개). 권한 700, 예전 파일은 `*.bak-1021`.
- AWS 비용은 크레딧으로 나가며 하루 약 1달러(10/12 기준 거친 값). 프로젝트가 끝나면 서버를 중지하거나 삭제할 것(중지해도 디스크와 고정 IP 요금은 남음).

- **관리자 운영 현황**(`https://54-116-113-17.sslip.io/admin-overview.html`, `admin.html` 제목 아래 링크): 체험 진행 현황(가입 → 대상 확인 → 건강정보 → 설문 제출 → 분석 결과 → 챌린지 시작 → 4주 완료의 단계별 인원), 날짜별 활동(신규 가입, 로그인 수, 로그인한 사용자 수, 재방문 사용자 수. 한국 시각 기준, 14/30/90일), 동의·삭제 현황, 서비스 상태(서버 가동 시각, DB 연결, 마이그레이션 번호, 관리자 수), 집계 CSV 내려받기. 모두 **숫자만**이고 이메일·사용자 번호·IP는 없음. 열람은 같은 관리자가 10분 안에 한 번만, CSV 내려받기는 매번 관리자 행위 기록에 남김. 날짜별 활동은 `access_logs`(93일 뒤 삭제)를 쓰므로 그 이전 날짜는 비고, 가입 수는 2026-10-12 이전 가입 날짜가 예전 시각 기록 오류로 부정확할 수 있음.
- **서버와 화면이 같이 바뀌는 변경**(예: 가입 요청)은 **서버 PR을 먼저 머지해 배포가 끝나길 기다린 뒤 바로 화면 PR을 머지**함. 가입 양식이 모르는 칸을 거절하므로(`extra="forbid"`) 한쪽만 나가면 가입이 짧게 안 됨. 지인 가입이 없는 시간에 하고, 마이그레이션이 든 쪽은 머지 직전에 `backup.sh`로 백업함. 2026-10-14에 #86(서버)→#87(화면) 순서로 했고, 배포 뒤 서버에서 마이그레이션(`e6f2c9a4d837`), 새 표 3개, 정책 v4, 관리자 권한 기록 4건, 로그인 IP, 폰트(`200`, `font/woff2`), 가입 시 동의 3건 기록을 확인함.
- **안드로이드 앱(시연용)**: `frontend/android`(Capacitor)에 있음. 서버의 CORS 허용 출처가 `localhost:5500`뿐이라, 앱은 `capacitor.config.json`의 `CapacitorHttp` 설정으로 웹뷰 대신 네이티브 통신을 써서 서버를 부름(서버를 바꾸지 않고 해결). 앱 화면 복사본(`frontend/www`)이 가입 요청 변경(2026-10-14)을 반영하지 않아 **앱에서는 가입이 안 되고 로그인만 됨**. 멘토님이 앱 대신 모바일 웹(PWA)을 권하셔서 앱은 시연용으로만 둠. GitHub 릴리스 `v1.0.0`에 APK(개발용 서명)가 있음.

### 팀원 사전 체험용 테스트 서버 (효민 맥북, 2026-10-22에 사용)

운영 서버와 DB·비밀값·주소를 모두 따로 둔 임시 서버. 날짜를 당겨 3일치 체험을 몇 분 만에 해 볼 때 씀.

1. **별도 폴더**(맥북): `git worktree add ~/paeon-demo origin/<브랜치>`. 작업 저장소와 섞이지 않고, compose 프로젝트 이름이 `paeon-demo`가 되어 컨테이너·볼륨이 따로 생김.
2. **`.env`는 새로 만듦**: DB 비밀번호, `JWT_SECRET`, `PII_*` 키를 모두 `openssl rand`로 새로 만들고 운영 값은 쓰지 않음. `DB_PORT=3307`(로컬 MySQL과 겹치지 않게), `DEMO_AUTOFILL=1`, `DEMO_AUTOFILL_END=…`.
3. **띄우기**: `docker compose up -d --build mysql fastapi`(Caddy는 운영 주소용이라 띄우지 않음) → `docker compose exec -T fastapi alembic upgrade head`.
4. **화면과 API를 한 주소로**: 작은 Caddy 컨테이너를 `paeon-demo_default` 네트워크에 붙여 `:8080`에서 `/v1/*`는 `fastapi:8000`으로, 나머지는 `frontend` 폴더를 내보냄.
5. **팀원에게 공유**: `cloudflared tunnel --url http://localhost:8080` → 출력의 `https://…trycloudflare.com` 주소. 터널 창을 닫거나 맥북이 잠들면 끊기므로 `caffeinate -dims`를 같이 켜 둠. 주소는 켤 때마다 바뀜.
6. **화면이 운영 서버를 부르지 않게 꼭 확인**: 화면 코드(`frontend/assets/api.js`, `common.js`)는 운영 주소(`https://54-116-113-17.sslip.io/v1`)를 박아 두고 있어, 그대로 두면 테스트 서버에서 연 화면이 **운영 DB에 가입·기록함**. 테스트 폴더에서만 그 문자열을 `location.origin + '/v1'`로 바꾸고 커밋하지 않음. 확인: 브라우저 개발자 도구 Network에서 요청 주소가 `…trycloudflare.com/v1/…`인지.
7. **날짜 당기기**: `DEMO_DAY_OFFSET`(서버의 "오늘"을 며칠 뒤로)은 **`feature/demo-day-offset` 브랜치에만** 있고 main에는 없음. `.env`에서 숫자를 바꾸고 `docker compose up -d --force-recreate fastapi`로 다시 만든 뒤, `docker compose exec -T fastapi python -c "from app.services.challenge_service import today_kst; print(today_kst())"`로 확인. 서버 전체에 걸리므로 **운영 서버에서는 절대 쓰지 않음**.
8. **알아 둘 것**: 자동 채움 패턴(꾸준함 → 흔들림 → 후반에 놓침)은 **그 서버에서 몇 번째로 마쳤는지**로 정해지므로, 미리 시험 삼아 3일을 끝까지 하면 순서가 밀림. 이미 쓰던 테스트 DB에서 브랜치를 바꿀 때는 `alembic current`와 `alembic heads`를 먼저 비교(코드가 DB보다 뒤처지면 500, 10/22 겪음).
9. **지우기**: 터널·`caffeinate` 창에서 `Ctrl + C` → `docker rm -f paeon-demo-web; cd ~/paeon-demo && docker compose down -v --rmi local` → `git worktree remove --force ~/paeon-demo`. `docker ps -a`, `docker volume ls`에 `paeon-demo`가 남지 않았는지 확인.

## 14. 남은 일

- 서버 전체 다운을 알려주는 외부 점검(예: GitHub Actions 주기 점검) 추가.
- **main 보호 규칙은 팀 결정으로 켜지 않음**(2026-10-13). main에 직접 push하면 리뷰 없이 바로 서버에 배포될 수 있고 강제 push도 막혀 있지 않음 → PR과 리뷰 관행을 유지하고, 사고가 나면 §6 롤백으로 대응. 쓰기 권한자 4명이 모두 admin이라, 필요하면 일부를 write로 내리는 것도 팀과 상의.
- 지인 체험이 끝난 뒤의 **삭제 순서**(날짜는 팀이 정함): (1) 혜림님 스크립트로 테스트 계정 삭제(미리보기 확인 뒤 `--apply`) → (2) 삭제 **뒤** 상태로 새 백업(`backup.sh`) → (3) 삭제 전에 만든 서버 백업 파일을 모두 지움 → (4) AWS 디스크 스냅샷 삭제 → (5) 맥북의 암호화 사본 삭제 → (6) 행 수와 남은 백업 목록 확인. 서버 백업을 지우는 스크립트는 아직 없음. 관리자 행위 기록(2년)과 서비스 접속 기록(3개월)은 처리방침대로 보관하므로 이 순서에서 지우지 않고, 비회원 문의는 30일 뒤 자동으로 삭제됨.
- **지인 체험 10/22~10/25.** 10/26 아침: `DEMO_AUTOFILL` 두 줄 지우고 fastapi 다시 만들기, 위 삭제 순서 시작(처리방침: 11/01까지 삭제). 자동 백업이 7일 남으므로 "삭제 전 백업 지우기"를 빼먹지 말 것. 서버 로그(접속 IP)는 3개월 보관이라 처리방침에 따로 적혀 있는지 확인.
- **IAM 계정**(멘토링 10/20): 팀원별 콘솔 계정(관리자 그룹 2명, 읽기 전용 그룹), MFA, 효민도 루트 대신 IAM 계정 사용.
- **API 보안 검사 남은 묶음**(§12): 관리자 묶음부터.
- 이메일 암호화 2단계(#158) 머지(10/24 동결 전). GitHub 2단계 인증(11/28까지 의무).
- 마이그레이션 사고 때 DB를 되돌리는 절차(`alembic downgrade` 또는 백업 복구)는 연습한 적이 없음.
- 서버 밖 자동 백업(S3 등)은 아직 없음.
- 요청 속도 제한은 로그인(§12), 비회원 문의(IP별), 커뮤니티 신고(하루 10건)에만 있음. 그 밖의 API에는 없음(학생 체험 수준에서는 위험이 낮다고 보고 알고만 있음).
- 정식 예측 흐름(`/v1/predictions/jobs`), 20명 이상의 동시 접속, 몇 시간 이상의 장시간 부하는 시험하지 않음. 체험 뒤 **테스트 서버**에서 `~/loadtest.py`로 잴 것(§13 동시 접속 한계).
- 화면이 연 주소에 맞춰 API 주소를 고르게 하는 규칙(운영 주소·앱은 운영 서버, 그 밖의 주소는 그 서버 자신)은 만들어 두었지만 PR은 안 함. 다시 테스트 서버를 띄울 일이 생기면 넣을지 팀과 정할 것(§13 테스트 서버 6번).
- **EBS 디스크 암호화는 2026-10-17에 끝남**(§11). 남은 정리: 며칠 안정적인 걸 본 뒤(10/20 멘토링 이후) 옛 볼륨 `paeon-root-OLD-unencrypted`와 **암호화되지 않은 스냅샷 2개**(10/8 것, `paeon-root-before-encrypt-1017`)를 삭제. 이걸 지워야 "암호화해 저장합니다"가 완전히 사실이 됨. 새 스냅샷 `paeon-root-encrypted-1017`은 암호화돼 있음.
- AWS 계정은 효민 개인 계정이고 크레딧(10/15 기준 약 $108, 2027-03-30쯤 만료)으로 운영해서 오즈 코딩스쿨 확인은 필요 없음. CloudTrail 트레일(S3 보관)과 세션 매니저는 학원에서 비용을 일부 지원해 주기로 함(10/20). 가능하면 SSH 접속을 PEM 키 대신 세션 매니저로 바꾸고 PEM 키는 폐기(멘토님 권장).
- 보류(2주 뒤인 10/27쯤 재논의): 무중단 배포, 서버가 꺼지면 알림이 멈추는 문제. 서버 밖 자동 백업(S3)은 **하지 않기로 함**(멘토님: 파이널 범위 밖, 백업 7일이면 충분).

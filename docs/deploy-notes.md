# 배포 인프라 노트 (작성: 효민 · 최초 2026-09-30 · 갱신 2026-10-07)

> 이 문서는 "서버에 무슨 일이 생겼을 때 효민님 없이도 팀원이 참고할 수 있게" 만든 기록입니다.
> **실제 비밀번호·키·웹훅 주소는 여기 안 적습니다.** 저장 위치만 안내합니다.

---

## 1. 서버 기본 정보

| 항목 | 값 |
|---|---|
| 리전 | 아시아 태평양(서울), ap-northeast-2 |
| 인스턴스 타입 | t3.small (최초 t3.micro가 메모리 부족이라 업그레이드, §7 참고) |
| 고정 IP (Elastic IP) | `54.116.113.17` — 서버를 껐다 켜도 안 바뀜 |
| OS | Ubuntu 26.04 LTS |
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
| `fastapi` | 백엔드 API, uvicorn 단일 프로세스(`--reload` 없음) | 메모리 상한 1GB, 밖에서 직접 접속 불가 |
| `mysql` | DB (MySQL 8.0), 데이터는 이름 붙은 볼륨에 보존 | 밖에서 직접 접속 불가 |

### 밖에 열려 있는 문 (보안 그룹, 2026-10-07 기준)

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
- 새 마이그레이션은 머지하는 순간 서버 DB에 적용되므로, **로컬에서 충분히 테스트한 뒤 push**할 것.
- 앱 코드가 아니라 `deploy.yml`만 바꾼 배포는 컨테이너가 바뀌지 않음(확인됨).
- `.env`나 compose 설정이 바뀌면 mysql·fastapi가 다시 만들어져 API가 **1분 남짓 끊길 수 있음**(컨테이너 시각에서 추정한 값, 측정값은 아님). DB 데이터는 볼륨에 그대로 있음.
- 확인: 저장소 **Actions 탭**(초록 체크 = 성공), 디스코드 알림.

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

## 6. DB

- DB명 `paeon`, 앱 계정 `paeon`. 앱은 컨테이너 내부 네트워크로 `mysql:3306`에 접속함.
- **서버 밖에서는 DB에 직접 접속할 수 없음**(3306 닫힘). 확인이 필요하면 서버에 SSH로 들어가서 `sudo docker compose exec mysql ...`로 접속.
- 비밀번호는 서버의 `~/AH_06_03/.env`에만 있음(`DB_PASSWORD`, `DB_ROOT_PASSWORD`). `.env`는 `.gitignore`에 있어 깃허브에 안 올라가고, **값은 채팅이나 문서에 붙여넣지 않음**.
- 2026-10-07에 root와 앱 계정 비밀번호를 새 값으로 교체함. 값은 서버 안에서 만들었고 옛 비밀번호가 차단되는 것을 확인함.
- 비밀번호 교체 원칙: 서버 안에서 생성 → 값을 명령줄에 쓰지 않고 입력 스트림으로 `ALTER USER` → `.env` 갱신 → `docker compose up -d --force-recreate fastapi` → 옛 비밀번호가 막혔는지, `alembic current`가 동작하는지 확인.

## 7. 트러블슈팅 기록 (같은 문제가 또 생기면 참고)

### 컨테이너가 갑자기 꺼져 있음 / 502 / `Killed` → 메모리 부족(OOM)
- 증상: `docker compose ps -a`에서 fastapi가 `Exited (137)`, 사이트 502, caddy 로그에 `lookup fastapi ... server misbehaving`.
- 확인: `sudo dmesg -T | grep -i "killed process"`, `free -h`, `sudo docker top ah_06_03-fastapi-1 -eo pid,ppid,rss,comm`(프로세스별 메모리).
- 1차(t3.micro): RAM 908MiB에 스왑 없음 → 스왑 추가 + t3.small(RAM 2GB)로 업그레이드.
- 2차(t3.small에서도 반복): uvicorn이 약 1.5GB까지 커져 종료됨. 프로세스별로 재 보니 `--reload` 감시용 uvicorn이 요청이 없어도 3분에 107MB씩 늘었음(재시작 직후 558MB vs 앱 92MB). `--reload` 제거 뒤에는 uvicorn 하나가 93MB로 3분간 변화 없음.
- 안전망: `restart: unless-stopped`, fastapi `mem_limit`/`memswap_limit` 1g. (원인 해결이 아니라 안전망. 장기 효과는 며칠 관찰 중)

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
- `restart: unless-stopped` 덕분에 컨테이너가 자동으로 올라옴. 그래도 `sudo docker compose ps`로 확인.
- Elastic IP라 주소는 그대로(`54.116.113.17`).

## 8. 점검 알림 (모니터링)

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

- 같은 문제가 2번 연속(약 5~10분) 이어질 때만 경고하고, 계속되면 60분마다 다시 알리고, 풀리면 복구 알림. 배포 중 컨테이너가 잠깐 바뀌어도 오경보가 안 나게 한 규칙.
- 연결 시험: `bash ~/paeon-monitor/check.sh test` → `204`가 나오고 채널에 테스트 메시지가 오면 정상.
- 경보 시험(임시 폴더라 실제 상태는 안 건드림): `DISK_LIMIT=1 STATE_DIR=/tmp/paeon-test bash ~/paeon-monitor/check.sh`를 2번 실행 → 경고 1건 확인 → `rm -rf /tmp/paeon-test`.
- 끄기: `crontab -l | grep -v paeon-monitor | crontab -`
- 한계: 서버 전체가 꺼지면 이 점검도 멈춰서 알릴 수 없음(외부에서 보는 점검은 아직 없음).

## 9. 보안 약속

- 밖에 열린 문은 **22, 80, 443**만. 규칙을 추가하기 전에 팀에 알리기. DB 포트는 열지 않고, DB 확인은 SSH로.
- 키, `.env` 값, 웹훅 주소, 토큰은 채팅·깃허브·디스코드에 붙여넣지 않음. **노출되면 지체 없이 폐기하고 새로 만듦.**
- `GUARDIAN_ENC_KEY`는 잃어버리면 보호자 정보를 못 여니, 서버 밖에 별도로 보관해 둘 것(담당: 효민). 값은 문서에 적지 않음.
- 서버에서 직접 고친 설정은 저장소에 반영(커밋)할 것.

## 10. 알아두면 좋은 것

- GitHub Secrets: `EC2_HOST`(=54.116.113.17), `EC2_SSH_KEY`(서버 접속 키), `DISCORD_WEBHOOK`(배포 알림용).
- 서버 변경은 가능하면 PR로 합의하고 한 PR로 묶어 머지 횟수를 줄이기.

## 11. 남은 일

- OOM 원인은 `--reload` 제거 뒤 3분 측정까지만 확인함 → 며칠 뒤 `restarts`, `oom`, fastapi 메모리 재확인, 요청이 들어올 때의 메모리 측정.
- 서버 전체 다운을 알려주는 외부 점검(예: GitHub Actions 주기 점검) 추가.
- 지인 테스트로 DB에 쌓인 건강정보의 정리 방침 결정.

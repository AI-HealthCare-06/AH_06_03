# 배포 인프라 노트 (작성: 효민, 2026-09-30)

> 이 문서는 "서버에 무슨 일이 생겼을 때 효민님 없이도 팀원이 참고할 수 있게" 만든 기록입니다.
> **실제 비밀번호·키 값은 여기 안 적습니다** — 저장 위치만 안내합니다.

---

## 1. 서버 기본 정보

| 항목 | 값 |
|---|---|
| 리전 | 아시아 태평양(서울), ap-northeast-2 |
| 인스턴스 타입 | t3.small (최초 t3.micro → 메모리 부족으로 업그레이드함, §6 참고) |
| 고정 IP (Elastic IP) | `54.116.113.17` — 서버를 껐다 켜도 안 바뀜 |
| OS | Ubuntu 26.04 LTS |
| 접속 계정 | `ubuntu` |

## 2. SSH 접속 방법

```bash
ssh -i ~/Downloads/paeon-new ubuntu@54.116.113.17
```

- 키 파일(`paeon-new`)은 **효민님 컴퓨터에만 보관**. 절대 채팅·깃허브·슬랙 등에 올리지 않기.
- 예전 키(`paeon.pem`)는 유출 사고로 폐기함 → 서버의 `~/.ssh/authorized_keys`에서 제거 완료, 지금은 `paeon-new`만 등록되어 있음.
- 보안 그룹의 SSH(22) 소스는 **"위치 무관(0.0.0.0/0)"으로 유지** — GitHub Actions가 매번 다른 IP에서 접속하기 때문에 특정 IP로 좁히면 자동배포가 깨짐. 대신 키 기반 인증만 허용되어 있어 실질적 위험은 낮음.

## 3. 서비스 구성 (`docker-compose.yml`)

서버의 `~/AH_06_03/docker-compose.yml`에 3개 컨테이너가 떠 있음:

| 서비스 | 역할 | 포트 |
|---|---|---|
| `fastapi` | 백엔드 API | 내부 8000 (외부 직접 노출 안 함, caddy 경유) |
| `mysql` | DB | 3306 |
| `caddy` | 리버스 프록시 + 자동 HTTPS | 80, 443 |

## 4. 배포 주소

- **외부 공개 주소(HTTPS)**: `https://54-116-113-17.sslip.io`
- **API 문서(Swagger)**: `https://54-116-113-17.sslip.io/docs`
- `sslip.io`는 도메인을 따로 안 사고 IP를 도메인처럼 쓰게 해주는 무료 서비스. `Caddyfile`(저장소 루트)에 이 주소가 등록되어 있고, Caddy가 Let's Encrypt에서 인증서를 자동 발급·갱신함.

## 5. 배포 방법

### 자동 배포 (기본)
- `main` 브랜치에 push(또는 PR 머지)되면 `.github/workflows/deploy.yml`이 자동 실행됨
- 내부 동작: GitHub Actions가 SSH로 서버 접속 → `git pull` → `docker compose up --build -d`
- 확인: 저장소 **Actions 탭**에서 실행 결과 확인 (초록 체크 = 성공)

### 수동 배포 (Actions가 안 될 때만)
```bash
ssh -i ~/Downloads/paeon-new ubuntu@54.116.113.17
cd ~/AH_06_03
git pull origin main
sudo docker compose up --build -d
sudo docker compose ps   # 전부 Up/healthy인지 확인
```

## 6. DB 정보

- Host: `54.116.113.17` / Port: `3306` / DB명: `paeon` / User: `paeon`
- **비밀번호는 서버의 `~/AH_06_03/.env` 파일에 있음** (DB_PASSWORD, DB_ROOT_PASSWORD) — 이 문서엔 안 적음
- root 비밀번호는 2026-09-30에 기본값에서 변경 완료 (데이터 손실 없이 `ALTER USER`로 교체함)
- `.env`는 `.gitignore`에 포함되어 있어 깃허브에 올라가지 않음 — 서버에만 존재

## 7. 트러블슈팅 기록 (같은 문제 또 생기면 참고)

### "Killed" / 컨테이너가 갑자기 꺼져 있음 → 메모리 부족(OOM)
- 증상: `docker compose ps`에 컨테이너가 안 보이거나 `Exited (137)`로 표시됨
- 원인: t3.micro(RAM 1GB)로는 MySQL+FastAPI(모델 로딩)+Caddy 동시 실행이 빠듯함
- 조치: ① 스왑 1GB 추가 ② 그래도 부족해서 인스턴스를 t3.small(RAM 2GB)로 업그레이드
- 확인 명령어: `free -h` (Mem 총량, Swap 총량 확인)

### 디스크 공간 부족 (`No space left on device`)
```bash
sudo docker system df          # 뭐가 용량을 먹는지 확인
sudo docker builder prune -af  # 빌드 캐시 정리 (제일 효과 큼)
sudo docker image prune -af    # 안 쓰는 이미지 정리
df -h /                        # 정리 후 남은 용량 확인
```

### 서버 재부팅(Stop→Start) 후 사이트가 안 열림
- 컨테이너는 재부팅 시 자동으로 안 켜짐 → SSH 접속 후 `sudo docker compose up -d` 직접 실행 필요
- 재부팅해도 Elastic IP는 안 바뀜 (`54.116.113.17` 그대로)

### `ModuleNotFoundError: No module named 'paeon_models'`
- 원인: `modeling/` 폴더가 Docker 이미지에 안 들어가고 있었음
- 조치: `app/Dockerfile`에 `COPY modeling ./modeling` + `ENV PYTHONPATH="/modeling:${PYTHONPATH}"` 추가

## 8. 알아두면 좋은 것

- GitHub Secrets에 `EC2_HOST`(=54.116.113.17), `EC2_SSH_KEY`(=paeon-new 키 내용)가 등록되어 있음 — 이게 CI/CD의 핵심
- DB·백엔드·Caddy 설정을 바꿀 땐 `docker-compose.yml`을 nano로 직접 고치기보다, 전체를 `cat > file << 'EOF' ... EOF`로 통째로 다시 쓰는 게 들여쓰기 실수를 막는 더 안전한 방법
- 모니터링/알림은 2차 사이클 작업으로 보류 중 (현재는 수동으로 Actions 탭·서버 상태 확인)

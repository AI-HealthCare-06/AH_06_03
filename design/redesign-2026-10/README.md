# PAEON 모바일 리디자인 시안 (2026-10-14)

Claude Design에서 만든 시안의 원본 파일이에요. 서비스(`frontend/`)에는 아직 반영하지 않았어요.

- 모바일 390px 기준 49개 화면 (사용자 화면 40개, 관리자 화면 8개, 디자인 시스템 1개)
- `canvas.json`: 화면 배치와 제목, `*.dc.html`: 화면별 원본
- 글꼴은 나눔고딕, 색은 파랑·크림 팔레트(디자인 시스템 화면 참고)

## 보는 방법

`.dc.html`은 Claude Design 전용 형식이라 브라우저에서 바로 열리지 않아요.
화면은 Claude Design 캔버스에서 보고, 이 폴더는 구현할 때 문구·색·간격을 확인하는 용도로 써요.

## 알아둘 점

- 파이·캐릭터 이미지는 Claude Design에 올린 파일(`/_blob/…`)이라 이 폴더에 들어 있지 않아요. 해당 화면 7개: Home, Menu, Pie, Challenge, ChallengeDetail, CharacterCreate, CommunityChallenges.
- 시안의 수치(참여 2,575명, 순위 등)는 예시 값이에요.
- 서버에 없는 기능: 파이(포인트), 배지, 캐릭터, 커뮤니티 피드·신고, 공통 챌린지, 파티, 관리자 신고·공통 챌린지 관리.
- 약관·처리방침 화면은 조항 제목만 있고 본문은 없어요. 본문은 `frontend/terms.html`, `frontend/privacy.html`을 써요.

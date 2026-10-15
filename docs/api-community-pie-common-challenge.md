# 커뮤니티 · 파이 · 공통 챌린지 API

모든 응답은 성공 `{"data": ...}`, 실패 `{"error": {"code", "message"}}`. 주소 앞에 `/v1`을 붙인다.
이용자 API는 로그인(Bearer) 필요, **건강정보 동의와는 상관없이** 쓴다. 관리자 API는 `ADMIN_EMAILS`에 있는 계정만(아니면 403).

## 이용자

### 닉네임
| 메서드·주소 | 설명 | 응답 |
|---|---|---|
| `GET /community/me` | 내 닉네임 | `{nickname: string\|null, pie_gift: 0}` |
| `PUT /community/me` `{nickname}` | 닉네임 정하기·바꾸기. 한글·영문·숫자·밑줄 2~10자. **처음 정할 때 파이 +10** | `{nickname, pie_gift: 10\|0}` |

에러: `NICKNAME_TAKEN`(409), 형식이 틀리면 `VALIDATION_ERROR`(422). 닉네임이 없으면 글·댓글·좋아요·공통 챌린지 참여가 `NICKNAME_REQUIRED`(409).

### 글·댓글·좋아요
| 메서드·주소 | 설명 |
|---|---|
| `GET /community/posts?category&sort&q&limit&offset` | `category`: diet·exercise·challenge·tips, `sort`: latest(기본)·popular(최근 30일 좋아요순), `q`: 제목·본문 검색. 응답 `{total, items[]}` |
| `POST /community/posts` `{category, title≤100, body≤1000}` | 글쓰기(201). **하루 3번까지 파이 +2**. 응답에 `pie_gain` |
| `GET /community/posts/{id}` | 상세 |
| `DELETE /community/posts/{id}` | 내 글 삭제(204). 좋아요·댓글·신고가 함께 지워짐 |
| `POST /community/posts/{id}/like` | 좋아요 토글 → `{liked, like_count}` |
| `GET·POST /community/posts/{id}/comments` | 댓글 목록 / 쓰기 `{body≤300}` |
| `DELETE /community/comments/{id}` | 내 댓글 삭제(204) |

글 항목: `post_id, category, title, preview, author_nickname, created_at, like_count, comment_count, liked_by_me, mine, hidden, notice`.
운영팀이 숨긴 글은 **작성자에게만** `hidden: true`, `notice: "운영 정책에 따라 숨김 처리됐어요"`로 보이고(본문은 비어 있음) 다른 사람 목록·상세에는 나오지 않는다. 삭제된 글은 아무에게도 안 보인다.

### 신고
`POST /community/posts/{id}/report`, `POST /community/comments/{id}/report` `{reason}` → 201 `{reported: true}`
`reason`: `health_info`(건강정보 포함) · `spam`(광고·스팸) · `abuse`(욕설·비방) · `other`(기타).
에러: `ALREADY_REPORTED`(409, 같은 대상 중복), `REPORT_OWN`(400, 내 글·댓글), 숨김·삭제된 대상은 404.

### 파이
| 메서드·주소 | 응답 |
|---|---|
| `GET /pie` | `{balance, recent[5]}` |
| `GET /pie/history?limit&offset` | `{balance, total, items[]}`, 항목 `{reason, delta, created_at}` |

`reason` 값: `welcome`(시작 선물) · `post_write`(글쓰기) · `common_challenge_rank`(순위 보상) · `common_challenge_complete`(완주 보상). 다른 기능이 늘면 이름이 늘어난다.

### 공통 챌린지
| 메서드·주소 | 설명 |
|---|---|
| `GET /common-challenges?state=active\|upcoming\|ended` | 목록 `{items[]}`: `challenge_id, title, proof_type, starts_on, ends_on, state, participants, max_reward, joined, my_rank` |
| `GET /common-challenges/{id}` | 목록 항목 + `target_steps, total_days, complete_min_days, rewards{first,second,third,complete}, my_days, certified_today, finalized, top[]`. `top`은 상위 5명 `{rank, nickname, days, is_me}`이고 내가 5위 밖이면 내 순위를 덧붙인다 |
| `POST /common-challenges/{id}/join` | 참여(201). 시작 전에도 가능, 끝난 뒤에는 불가 |
| `POST /common-challenges/{id}/certify` `{steps?}` | 오늘 인증(201) → `{my_days, my_rank}` |

- `proof_type`: `steps`(걸음 수, `steps`가 목표 이상이어야 인증) · `self`(직접 인증, 숫자 없이).
- 하루 한 번(한국 날짜), 기간 안에서만. 순위는 **인증 일수가 많은 순 → 같으면 그 일수에 먼저 도달한 사람**. 걸음 수 같은 값은 목록·순위에 내보내지 않는다.
- 에러: `NOT_JOINED` · `ALREADY_JOINED` · `ALREADY_CERTIFIED` · `COMMON_CHALLENGE_NOT_ACTIVE` · `COMMON_CHALLENGE_ENDED`(409), `STEPS_REQUIRED` · `STEPS_NOT_ENOUGH`(422), `COMMON_CHALLENGE_NOT_FOUND`(404).

## 관리자

### 신고 처리
| 메서드·주소 | 설명 |
|---|---|
| `GET /admin/reports?status=pending\|done&limit&offset` | 글·댓글 **대상별로 묶어서** `{total, pending_total, items[]}`. 항목: `target_type(post\|comment), target_id, title, author_nickname, category, report_count, pending_count, reasons{사유:건수}, preview, status, action, last_reported_at`. 댓글이면 `title`·`category`는 달린 글의 것 |
| `POST /admin/reports/{target_type}/{target_id}/action` `{action}` | `hide`(숨김) · `delete`(삭제, 내용을 비움) · `dismiss`(문제 없음) → `{target_type, target_id, action, handled}`. 이미 처리했으면 `REPORT_ALREADY_HANDLED`(409) |

`pending_total`은 관리자 메뉴의 숫자("커뮤니티 신고 2")로 쓴다.

### 공통 챌린지 관리
| 메서드·주소 | 설명 |
|---|---|
| `GET /admin/common-challenges` | 전체 목록(이름·기간·인증 방식·상태·참여 인원·완주 기준·보상·확정 시각) |
| `POST /admin/common-challenges` | 만들기(201). `title, proof_type, target_steps(steps일 때 필수), starts_on, ends_on, complete_min_days?(비우면 전체 일수의 70% 올림), reward_first/second/third/complete(기본 300/200/100/20)` |
| `PATCH /admin/common-challenges/{id}` | `title, complete_min_days, reward_*`만 수정(기간·인증 방식은 못 바꿈). 확정 뒤에는 `COMMON_CHALLENGE_FINALIZED`(409) |
| `POST /admin/common-challenges/{id}/finalize` | **끝난 뒤** 순위 확정 → 1·2·3위에게 순위 보상, 그 밖에 인증 일수가 `complete_min_days` 이상인 사람에게 완주 보상을 파이로 적립. 한 번만. 응답 `{ranked, completed, total_pie}`. 순위 보상을 받은 사람은 완주 보상을 따로 받지 않는다 |

에러: `COMMON_CHALLENGE_NOT_ENDED`(409, 끝나기 전), `COMMON_CHALLENGE_FINALIZED`(409, 이미 확정).

### 관리자 행위 기록
기록에는 대상 번호 끝 8자만 남고 글·댓글 내용은 남지 않는다. 동작 이름: `community_reports_view`, `community_report_hide|delete|dismiss`, `common_challenges_view`, `common_challenge_create|update|finalize` (한글 이름표는 `admin.html`의 `ACTION_LABEL`에 있음).

## 정리 규칙
- **회원 탈퇴**: 닉네임·글·댓글·좋아요·신고·파이·공통 챌린지 참여와 인증이 모두 삭제된다.
- **건강정보 동의 철회**: 닉네임·글·댓글·좋아요·신고는 남고, **파이 장부와 공통 챌린지 참여·인증은 삭제**된다(건강 활동에서 나온 기록). 새 표를 만들 때는 `account_service.HEALTH_KEEP_TABLES`에 이름을 넣으면 철회 때 남고, 넣지 않으면 지워진다.

## 이번 범위에 없는 것
사진 첨부, 파티, 배지, 캐릭터, 기존 4주 챌린지의 파이 적립(+5, +10, +50). 파이 적립은 `pie_service.add(db, user_id, delta, reason, ref_key)`를 부르면 되고, 같은 (회원, reason, ref_key)는 한 번만 적립된다.

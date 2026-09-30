# 다음 실행 전에 읽을 파일

진행자는 편집 사례를 시작하기 전에 아래 파일을 **실제로 읽고** SHA-256을 다시 계산해 이 표와 대조한 뒤, 결과를 새 JSONL 작업 기록에 남긴다.
다르면 멈추고 사용자에게 알린다. `judgments.jsonl`과 `cases/`가 생긴 뒤에는 그것도 읽는다 (아직 없음).

검증 명령 (저장소의 `editing_lab/`에서): `sha256sum -c NEXT_RUN.sha256`

## 1. 인수인계와 원자료 (원본, 수정 금지)

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `handoff/2026-09-30_v2/짧은글_편집실험_인수인계_2026-09-30_002.md` | `85d4d40437109c1a4ba08ac0490c5e7f0a63cf68c36794d2eed462824e597dab` | 목적과 우선순위의 기준. v2가 앞선 인계보다 우선 |
| `handoff/2026-09-30_v2/variants.json` | `928abbab5c5b7b801f1327dff97495b3dfdf0f6ac4b82ceff56e273d2f1b3b2c` | 211자 초고, A(161자), B(211자) 원자료. 직접 비교는 초고 대 B |
| `handoff/2026-09-30_v2/manifest.json` | `ecf91f116ab1a96a0e34a94b2dc083e3ab82c43f911d4e03d91839a9fb52e206` | 위 두 파일의 원래 경로와 SHA-256 |
| `handoff/2026-09-30_v2/수신확인_지시.txt` | `4855edfca3d2ff5bc6fa83757114759828734663c59fc6a899143598a2954ffe` | 수신 증거로 낼 항목 |
| `sources/handoff_check_2026-09-30.md` | `dcf62d5984562ff3d6e83aa79956ddbdac8fc85e3fb43323af9a9e1937f24d7f` | 인수인계서 점검 결과: 받지 못한 자료, 다듬을 점 |

## 2. 역할과 절차 (3판)

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `roles/v3/common_rules.md` | `7239ddbb593485919663f0d98ef5646c3f1392bde5fd67c46622b5aff623ac5e` | 모든 역할 공통 규칙 |
| `roles/v3/moderator.md` | `a4f1f67feb93e93744beb9f4f3b63a4eac455bc2a828f2136ad0e32aaf5941cd` | 진행자 |
| `roles/v3/reviewer_1_purpose_expression.md` | `c9a26489b76b4270880842eb8f17e4ea4b4a56df2d52823ce52b0f99cde16401` | 에이전트 1 |
| `roles/v3/reviewer_2_order.md` | `c0186042f23f48784ffdb141969956436a17b12c9b13277a8f075ee2ff076293` | 에이전트 2 |
| `roles/v3/reviewer_3_fidelity.md` | `0df2d33cb1336abb115d733e01cf10bf8fa24d9cff04829e6651903522cf7252` | 에이전트 3 |
| `PROTOCOL_v3.md` | `13eb326a8238cabd0d66d71e1f07436dd2c9fb1470139818ab59f5b16d58053e` | 토론과 피드백 절차 |
| `templates/case_template_v3.md` | `27af49b2555c2f4b2afcb0205e5fa8307c1f28c64cdf82a9312d2c4fec256682` | 사례 기록 양식 |

## 3. 논문 적용 기준 (3판)과 읽은 범위

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `criteria/v3/moderator_criteria_v3.md` | `0c70f8a2d2119049714b0b5a95a90b6e27bbccb2750f921b668cdfd415110af8` | Self-Refine, 사람 피드백 요약 학습 |
| `criteria/v3/reviewer_1_criteria_v3.md` | `691dd03b7edf5a6b2d74aca7a172f0d8a86fe05b55bbc7ea5b8be1da2b1c9511` | 에이전트 1이 작성 |
| `criteria/v3/reviewer_2_criteria_v3.md` | `abd7fec651ff884576f2f49b12d4b30e1e3d391473a96966ccc490bf4ca83b2e` | 에이전트 2가 작성 |
| `criteria/v3/reviewer_3_criteria_v3.md` | `fdbdd6864aae5cc5cac23c14f9d2d7ba731824928d38a18be70d6f457f806568` | 에이전트 3이 작성 |
| `sources/SOURCES.md` | `7f8ee54f1838bdde21d184951e0722c740ae36adb5fde3cd1a7320a68946c258` | 논문 본문 미확인 범위 |

## 4. 에이전트 수신 확인 (2026-09-30)

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `receipts/2026-09-30/reviewer_1.md` | `bbfab984fda376b062a7466e6b6c88f0acfb63cfb112661bf4215009d6e7e09d` | 에이전트 1의 읽기와 역할 이해 |
| `receipts/2026-09-30/reviewer_2.md` | `ad45a8d09d0e7dd3589c13bced0c608ff7b95b76bcb1906646eb40c3bf0d60c4` | 에이전트 2의 읽기와 역할 이해 |
| `receipts/2026-09-30/reviewer_3.md` | `d646ec848cc8b99691dfdd92964d72377bb0c05e05e75829d5d1ca47d3a77d8b` | 에이전트 3의 읽기와 역할 이해 |
| `receipts/2026-09-30/SUMMARY.md` | `333767a16839173ebfc84c887a125a6cd9d75147ac9341fc23c3dfc75861fe1b` | 진행자 대조 결과와 아직 정하지 않은 질문 Q1~Q16 |

## 아직 없는 것

- 기존 토론 보고서 `report.md`와 기존 논문 검토 자료: 사용자가 추가로 전달한 뒤 `handoff/`에 새 폴더로 보관하고 이 목록에 더한다.
- 논문 본문: 네트워크 정책으로 읽지 못함 (`sources/SOURCES.md`).
- 3.1판: `receipts/2026-09-30/SUMMARY.md`의 질문에 사용자가 답한 뒤 만들고, 세 에이전트의 수신 확인을 다시 받는다.

이전 판(1판 복원본 `versions/v1_restored/`, 2판 `roles/*.md` 등)은 기록용이며 실행 때 읽지 않는다.

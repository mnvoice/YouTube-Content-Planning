# 다음 실행 전에 읽을 파일 (3.1판 기준)

진행자는 편집 사례를 시작하기 전에 아래 파일을 **실제로 읽고**, 저장소의 `editing_lab/`에서 `sha256sum -c NEXT_RUN.sha256`을 실행해 이 표와 대조한 뒤 결과를 새 JSONL 작업 기록에 남긴다.
다르면 멈추고 사용자에게 알린다. `judgments.jsonl`과 `cases/`가 생긴 뒤에는 그것도 읽는다 (아직 없음).
검토 에이전트를 새 세션에서 다시 만들 때는 README의 '새 세션에서 이어 갈 때' 순서를 따른다.

## 1. 인수인계와 원자료 (원본, 수정 금지)

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `handoff/2026-09-30_v2/짧은글_편집실험_인수인계_2026-09-30_002.md` | `85d4d40437109c1a4ba08ac0490c5e7f0a63cf68c36794d2eed462824e597dab` | 목적과 우선순위의 기준 |
| `handoff/2026-09-30_v2/variants.json` | `928abbab5c5b7b801f1327dff97495b3dfdf0f6ac4b82ceff56e273d2f1b3b2c` | 211자 초고, A(161자), B(211자). 직접 비교는 초고 대 B |
| `handoff/2026-09-30_v2/manifest.json` | `ecf91f116ab1a96a0e34a94b2dc083e3ab82c43f911d4e03d91839a9fb52e206` | 위 두 파일의 원래 경로와 SHA-256 |
| `sources/handoff_check_2026-09-30.md` | `dcf62d5984562ff3d6e83aa79956ddbdac8fc85e3fb43323af9a9e1937f24d7f` | 인수인계서 점검 결과: 받지 못한 자료, 다듬을 점 |

## 2. 역할과 절차 (3.1판, 현재 기준)

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `roles/v3.1/common_rules.md` | `e53ca84ab4b6c917ccf0403f8c1b3ca44b97f38e6e6111ab35203798d836defb` | 모든 역할 공통 규칙, Q1~Q16 처리 규칙, 논문 읽기 상태 |
| `roles/v3.1/moderator.md` | `8b0e40b44ec72e3b6cde9f8920b3d99935c26a266c94ed5d3d7634c83faf0405` | 진행자, Self-Refine·사람 피드백 연구 적용 |
| `roles/v3.1/reviewer_1_purpose_expression.md` | `64ecef3986eb20f175e7008c46e69154318d804cd7c71352e337603751f73020` | 에이전트 1, Flower–Hayes 기준 |
| `roles/v3.1/reviewer_2_order.md` | `524a39a5f5169b6e219829ce1ef6ac78a474c4a0c8e2c0eb30eef9f3ab9b2401` | 에이전트 2, DOC 기준 |
| `roles/v3.1/reviewer_3_fidelity.md` | `8a7362aad61093586b0a9da431cd5e74e1db75c5129dd1104115931bd208cf91` | 에이전트 3, SummEval 기준 |
| `PROTOCOL_v3.1.md` | `8466535fd7688dc438e926ec62b9a6dfb411cd3002e7b0807c1d6e75eb916787` | 독립 검토 → 상호 반론 → 조정 → 진행자 정리 → 사용자 반응 → 판단 갱신 |
| `templates/case_template_v3.1.md` | `cfabc7f202a8c30abb27018c64cb3e367987bda8554d8b7ed1a142f561e1b395` | 사례 기록 양식 |

## 3. 논문 기준과 읽은 범위

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `criteria/v3.1/PAPER_MAP.md` | `04a449bc4f6a3f6d58c54deb6da9ba7dad851c1f6864903412694af00c441982` | 논문별 적용 역할·절차, 직접/응용 구분, README/본문 읽기 상태 |
| `criteria/v3/moderator_criteria_v3.md` | `0c70f8a2d2119049714b0b5a95a90b6e27bbccb2750f921b668cdfd415110af8` | 진행자 기준 카드 |
| `criteria/v3/reviewer_1_criteria_v3.md` | `691dd03b7edf5a6b2d74aca7a172f0d8a86fe05b55bbc7ea5b8be1da2b1c9511` | 에이전트 1이 작성 |
| `criteria/v3/reviewer_2_criteria_v3.md` | `abd7fec651ff884576f2f49b12d4b30e1e3d391473a96966ccc490bf4ca83b2e` | 에이전트 2가 작성 |
| `criteria/v3/reviewer_3_criteria_v3.md` | `fdbdd6864aae5cc5cac23c14f9d2d7ba731824928d38a18be70d6f457f806568` | 에이전트 3이 작성 |
| `sources/SOURCES.md` | `7f8ee54f1838bdde21d184951e0722c740ae36adb5fde3cd1a7320a68946c258` | 논문 본문 미확인 범위, 차단된 호스트 |

## 4. 에이전트 수신 확인

| 파일 | SHA-256 | 읽는 이유 |
|---|---|---|
| `receipts/2026-09-30/SUMMARY.md` | `333767a16839173ebfc84c887a125a6cd9d75147ac9341fc23c3dfc75861fe1b` | 3판 수신 확인 대조와 질문 Q1~Q16 |
| `receipts/2026-09-30_v3.1/reviewer_1.md` | `6897d815fe84279d7dec062e50e62ae54135d0d06f8d7a89739c907cb0de9a90` | 에이전트 1의 3.1판 수신 확인 |
| `receipts/2026-09-30_v3.1/reviewer_2.md` | `5105a53b5b43fec6b7a31a74b339610a7063717b0ec97f248e5f3c8c73dc28ec` | 에이전트 2의 3.1판 수신 확인 |
| `receipts/2026-09-30_v3.1/reviewer_3.md` | `009eb638314fc11b977cb476fe9783ef7db03b49b47bac02dfe279b159f7f36f` | 에이전트 3의 3.1판 수신 확인 |
| `receipts/2026-09-30_v3.1/SUMMARY.md` | `be88b62caffa5270ff5d44d3355a547dc6b2ab64a99ba04d2de19ac6f22ed550` | 3.1판 수신 확인 대조 |

## 아직 없는 것

- 기존 토론 보고서 `report.md`와 기존 논문 검토 자료: 사용자가 전달하면 `handoff/`에 새 폴더로 보관하고, 세 에이전트가 읽게 한 뒤 이 목록에 더한다. 그 전에는 내용을 추측하지 않는다.
- 논문 본문: 네트워크 정책으로 읽지 못함 (`sources/SOURCES.md`, `criteria/v3.1/PAPER_MAP.md`).

이전 판(1판 복원본 `versions/v1_restored/`, 2판 `roles/*.md`, 3판 `roles/v3/` 등)은 기록용이며 실행 때 읽지 않는다.

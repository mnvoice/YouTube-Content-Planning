# 짧은 글 편집 실험실

같은 내용을 유지하면서 조사, 어순, 어미, 문장 호흡, 문장과 문단 배치, 정보 공개 시점, 강조와 종결을 조금씩 고쳐
더 이해하기 쉽고 자연스럽게 읽히며 관심과 여운이 남는 글을 만드는 **방법**을 발전시키기 위한 역할 구성과 작업 기준입니다.

현재 상태 (2026-09-30): **역할 정비(3판)와 에이전트 수신 확인 단계.** 편집 사례는 아직 진행하지 않았고, 편집 효과를 검증한 것도 아닙니다.
후속 지시를 받으면 `NEXT_RUN.md`의 파일을 먼저 읽고 `PROTOCOL_v3.md` 순서로 시작합니다.

## 기준 문서

- 인수인계서 v2와 원자료: `handoff/2026-09-30_v2/` (받은 그대로 보관, 수정 금지)
- 실행 전 읽기 목록과 SHA-256: `NEXT_RUN.md`

## 구성 (3판, 현재 기준)

| 역할 | 기반 논문 | 지시문 | 기준 카드 |
|---|---|---|---|
| 진행자 (주 에이전트) | Self-Refine, 사람 피드백 요약 학습 (절차에 반영) | `roles/v3/moderator.md` | `criteria/v3/moderator_criteria_v3.md` |
| 에이전트 1 — 목적·수정 과정 + 문장 표현 (조사, 어순, 어미, 문장 호흡) | Flower & Hayes (1981). 한국어 표현 판단은 별도 응용 판단 | `roles/v3/reviewer_1_purpose_expression.md` | `criteria/v3/reviewer_1_criteria_v3.md` |
| 에이전트 2 — 배치와 정보 공개 | Yang 외 (2023) DOC | `roles/v3/reviewer_2_order.md` | `criteria/v3/reviewer_2_criteria_v3.md` |
| 에이전트 3 — 의미 보존과 읽기 품질 | Fabbri 외 (2021) SummEval | `roles/v3/reviewer_3_fidelity.md` | `criteria/v3/reviewer_3_criteria_v3.md` |

모든 역할은 `roles/v3/common_rules.md`를 먼저 따릅니다.

## 판 이력 (이전 판은 보존)

| 판 | 위치 | 비고 |
|---|---|---|
| 1판 | 파일 없음 (SHA-256만 `logs/setup_2026-09-30.jsonl`에) | 인수인계서 없이 작성 |
| 2판 | `roles/*.md`, `PROTOCOL.md`, `templates/case_template.md`, `criteria/*.md` | 에이전트 기준 카드의 지적 6건 반영 |
| 3판 | `roles/v3/`, `PROTOCOL_v3.md`, `templates/case_template_v3.md`, `criteria/v3/` | 인수인계서 v2와 2026-09-30 사용자 지시 반영 |

## 새 세션에서 이어 갈 때

클라우드 세션은 끝나면 사라집니다. 이 폴더의 파일이 원본입니다.

1. 주 에이전트가 진행자를 맡고 `NEXT_RUN.md`의 목록을 실제로 읽어 SHA-256을 대조한다.
2. 검토 에이전트 세 개만 만든다. 각자에게 `roles/v3/common_rules.md`, 자기 3판 지시문, `PROTOCOL_v3.md`, 인수인계서 v2, `variants.json`, 자기 3판 기준 카드를 읽게 하고 수신 확인을 받는다.
3. 다시 만든 사실과 읽은 파일의 SHA-256을 `logs/`의 새 JSONL 파일에 남긴다.

## 폴더

```
NEXT_RUN.md             실행 전 읽기 목록 (파일, SHA-256, 읽는 이유)
PROTOCOL_v3.md          토론과 피드백 절차 3판 (PROTOCOL.md는 2판)
handoff/                받은 인수인계 묶음 (원본 그대로)
roles/v3/               역할 지시문 3판 (roles/*.md는 2판)
criteria/v3/            논문 적용 기준 3판 (검토자 카드는 각 에이전트가 작성)
receipts/               에이전트 수신 확인 보고 (받은 그대로)
sources/                읽은 범위, 인수인계서 점검 결과
templates/              사례 기록 양식
logs/                   JSONL 작업 기록
cases/                  (사례를 시작하면 생김) 사례 기록
judgments.jsonl         (첫 사용자 반응 뒤 생김) 다음 편집에 적용할 조건
```

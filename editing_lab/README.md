# 짧은 글 편집 실험실

같은 내용을 유지하면서 조사, 어순, 문장 호흡, 문장과 문단 배치, 정보 공개 시점을 조금씩 고쳐
더 이해하기 쉽고 읽기 좋은 글을 만드는 **방법**을 발전시키기 위한 역할 구성과 작업 기준입니다.

현재 상태: **준비 단계 완료 (2026-09-30)**. 편집 사례는 아직 진행하지 않았습니다. 후속 지시를 받은 뒤 `PROTOCOL.md` 순서로 시작합니다.

## 구성

| 역할 | 기반 논문 | 지시문 | 기준 카드 |
|---|---|---|---|
| 진행자 (주 에이전트) | Self-Refine, 사람 피드백 요약 학습 (절차에 반영) | `roles/moderator.md` | `criteria/moderator_criteria.md` |
| 에이전트 1 — 글의 목적과 수정 과정 | Flower & Hayes (1981) | `roles/reviewer_1_purpose.md` | `criteria/reviewer_1_criteria.md` |
| 에이전트 2 — 배치와 정보 공개 | Yang 외 (2023) DOC | `roles/reviewer_2_order.md` | `criteria/reviewer_2_criteria.md` |
| 에이전트 3 — 의미 보존과 읽기 품질 | Fabbri 외 (2021) SummEval | `roles/reviewer_3_fidelity.md` | `criteria/reviewer_3_criteria.md` |

모든 역할은 `roles/common_rules.md`를 먼저 따릅니다.

## 새 세션에서 이어 갈 때

클라우드 세션은 끝나면 사라집니다. 이 폴더의 지시문이 원본이며, 새 세션에서는 다음 순서로 역할을 다시 만듭니다.

1. 주 에이전트가 진행자를 맡고 `roles/moderator.md`, `PROTOCOL.md`, `judgments.jsonl`(있으면)을 읽는다.
2. 검토 에이전트 세 개만 만든다. 각자에게 `roles/common_rules.md`와 자기 역할 지시문, 자기 기준 카드를 읽게 한다.
3. 다시 만든 사실과 읽은 파일의 SHA-256을 `logs/`의 새 JSONL 파일에 남긴다.

## 폴더

```
PROTOCOL.md             사례 한 건의 진행 순서, 기록 파일 규칙
roles/                  역할 지시문 (공통 규칙, 진행자, 검토자 3)
criteria/               논문 기준 카드 (검토자 카드는 각 에이전트가 직접 작성)
sources/SOURCES.md      읽은 범위와 확인하지 못한 범위, 막힌 것을 푸는 방법
templates/              사례 기록 양식
logs/                   JSONL 작업 기록
cases/                  (사례를 시작하면 생김) 사례 기록
judgments.jsonl         (첫 사용자 반응 뒤 생김) 다음 편집에 적용할 조건
```

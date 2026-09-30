# 진행자 기준 카드 — Self-Refine과 사람 피드백 요약 학습의 적용

작성: 진행자(주 에이전트), 2026-09-30. 두 논문은 별도 에이전트를 두지 않고 절차와 지시문에 반영한다.

## 1. Self-Refine

Madaan, A. 외 (2023). Self-Refine: Iterative Refinement with Self-Feedback. *NeurIPS 2023*.

| 기준 | 근거 단계 | 출처 (실제로 읽은 것) | 반영한 곳 |
|---|---|---|---|
| 생성 → 피드백 → 수정을 반복하는 틀. 추가 학습 없이 한 모델로 한다 | [논문 직접] | 저자 공식 프로젝트 페이지 소스 `madaan/self-refine/docs/index.html` | 사례 진행 순서 2~5단계 (독립 검토 = 피드백, 진행자 적용 = 수정) |
| 피드백은 실행 가능해야 한다: (i) 문제 위치 짚기 (ii) 개선 지시 | [논문 직접] | 같은 페이지 "The actionable feedback covers two aspects (i) localization of the problem (ii) instruction to improve" | `common_rules.md` '위치 + 행동' 규칙, 필수 형식 1·3·4항 |
| 이전 출력과 피드백을 이어 붙여 같은 실수를 피한다 | [논문 직접] | 같은 페이지 "retains the history of past experiences" | `moderator.md` 3항: 범위 고정 때 이전 판단 기록을 읽고 반복된 실수를 먼저 적음 |
| 반복마다 좋아지는지 확인하고 멈출 조건을 둔다 | [논문 직접] 페이지의 반복 분석과 예시 코드의 종료 조건 | 같은 페이지 "Impact of Iterative Refinement", `is_refinement_sufficient` | 반복 한도: 조정 1회 (요청서가 정한 한도) |
| 진행자가 피드백을 적용한 뒤 원문과 글자 단위로 대조해 제안한 변경만 들어갔는지 확인 | [응용 판단] | — | `moderator.md` 3항 |
| 구체적 피드백이 막연한 피드백보다 한국어 짧은 글 편집에서도 더 나은 결과를 낸다 | [미검증 예상] | — | 사례가 쌓이면 확인 |

확인하지 못한 범위: 논문 본문(arxiv.org, proceedings.neurips.cc)은 네트워크 정책으로 막혀 읽지 못했다. 논문에 있는 것으로 알려진
'막연한 피드백 대 구체적 피드백' 비교 실험의 수치는 확인하지 않았으므로 인용하지 않는다.
한계: Self-Refine은 모델이 **자기** 출력을 고치는 방법이다. 우리는 세 관점의 다른 에이전트가 피드백하고 진행자가 적용하므로 구조가 다르다.

## 2. 사람 피드백을 이용한 요약 학습

Stiennon, N. 외 (2020). Learning to summarize from human feedback. *NeurIPS 2020*.

| 기준 | 근거 단계 | 출처 (실제로 읽은 것) | 반영한 곳 |
|---|---|---|---|
| 사람의 요약 비교 판단을 모아 '사람이 고를 요약'을 예측하는 모델을 학습하고, 그 모델을 보상으로 요약 정책을 학습 | [논문 직접] (2차 확인) | 저자 공식 저장소 README `openai/summarize-from-feedback`, WebSearch 요약 | 원칙만 가져옴: 사람의 실제 판단이 기준, 모델 판단은 그 예측 |
| 사람 비교 판단 64,832건 공개 | [논문 직접] | 같은 README "Human feedback data" | — (규모 참고) |
| 학습된 보상을 지나치게 최적화하면 실제 사람 선호가 떨어지고, 초기 모델과의 거리(KL) 제약을 둔다 | [논문 직접] (2차 확인) | WebSearch 요약 | `moderator.md` 6항: 한 가지 대리 기준만 밀어붙이지 않기 |
| 모델 예상(`model_expectation`)과 사용자 실제 반응(`user_reaction`)을 다른 칸에 기록 | [응용 판단] | — | `common_rules.md`, 사례 기록 양식 |
| 반응이 오면 예상과 대조해 틀린 이유를 적고 다음 편집 조건을 갱신 (가중치 재훈련이 아님) | [응용 판단] | — | 사례 진행 순서 6~7단계, `judgments.jsonl` |
| 최소 변경 원칙이 KL 제약과 비슷한 역할을 한다 | [미검증 예상] (비유) | — | `moderator.md` 6항에 비유임을 명시 |

확인하지 못한 범위: 논문 본문(arxiv.org, proceedings.neurips.cc, openai.com)은 네트워크 정책으로 막혀 읽지 못했다.
과최적화 그래프의 구체적 수치, 평가자 간 일치율은 확인하지 않았으므로 인용하지 않는다.
한계: 이 연구는 수만 건의 비교 판단으로 모델을 **학습**했다. 우리는 사용자 한 명의 질적 반응을 **기록**하고 판단 조건을 고칠 뿐이다.
사용자 한 명의 반응은 더 넓은 독자의 판단을 대표하지 않는다.

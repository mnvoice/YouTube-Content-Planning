# 독자에게 배우기: 에이전트 취향이 아니라 독자 반응으로 표현 고르기

지금까지는 벤치마크 자료를 넣으면 에이전트가 고르는 표현(제목 구조, 첫 문장 방식 등)이 **달라지는 것**까지 확인했습니다.
다음 질문은 **그렇게 달라진 선택이 우리 독자(시청자)에게 도움이 됐는가**입니다.

에이전트끼리 "좋은 글"이라고 합의한 결과만 쌓으면, 채널은 독자가 아니라 에이전트 취향에 맞춰집니다.
이 문서는 그 위험의 근거, 시스템이 판단하는 방식, 도구(`feedback` 명령) 사용법, 참고 논문을 정리합니다.

## 1. 합의만 쌓으면 무엇이 쌓이나

| 위험 | 무슨 일이 생기나 | 근거 |
|---|---|---|
| 자기 선호 | AI 평가자는 AI가 쓴 글, 특히 자기 글을 더 높게 칩니다. 사람 평가는 같아도 그렇습니다. | Panickssery 외 2024, Laurito 외 2025 |
| 함께 틀림 | 모델들은 틀릴 때 같은 답으로 틀리는 경우가 많습니다. 에이전트 둘이 합의해도 독립적인 확인 두 번이 아닙니다. | Kim 외 2025, Eisenstein 외 2024 |
| 기준 과최적화 | 대리 기준(에이전트 점수)을 계속 올리면 어느 순간부터 진짜 목표(독자 만족)는 떨어집니다. | Gao 외 2023 |
| 획일화 | AI가 고른 글만 다시 AI의 본보기가 되면 표현의 폭이 좁아집니다. | Padmakumar·He 2024, Shumailov 외 2024 |
| 가짜 독자 | 에이전트에게 "50대 독자인 척" 시켜도 실제 집단 반응을 잘 못 맞히고, 오히려 평평하게 뭉갭니다. | Wang 외 2025, Maiorano 2026 |

실제 데이터로 확인된 사례도 있습니다. 미국 매체 Upworthy의 제목 A/B 테스트 1만 7천여 건에서, AI에게 "어느 제목이 이길지" 물으면
성적이 나빴고, 가장 나은 AI 단독 방법도 우연보다 **약간** 나은 수준이었습니다. 반면 AI의 예측을 출발점으로 쓰고 실제 독자 반응으로 고쳐 나가는 방식은
독자 수가 적을 때 가장 좋았습니다 (Ye 외 2025, LOLA). **에이전트 판단은 버릴 것이 아니라, 독자가 채점할 '예측'으로 써야 합니다.**

반대쪽 함정도 있습니다. 독자 반응 중 **클릭만** 보면 부정적·자극적인 제목이 이깁니다 (Robertson 외 2023: 부정적 단어 하나당 클릭률 약 2.3% 증가).
YouTube 추천도 같은 이유로 클릭보다 시청 시간을 봅니다 (Covington 외 2016). 그래서 이 도구는 클릭률이 아니라
**시청 시간 점유율**(YouTube A/B 테스트 판정 기준)과 **이해도**(독자 패널)를 독자 결과로 씁니다.

## 2. 시스템이 생각하는 방법

한 줄 요약: **에이전트 판단은 가설, 독자 반응은 채점, 장부는 둘의 차이를 재는 곳.**

```
 표현 후보 ──▶ 에이전트 예측 ──▶ 시험 후보 고르기 ──▶ 독자 결과 ──▶ 채점
 (script)     (따로, 결과 전에)   (합의 후보 + 반대 후보)  (A/B·패널)      │
    ▲                                                                     │
    └── 확인된 것만 다음 프롬프트로 ◀── 표현 유형별 학습 ◀── 에이전트별 적중률 ◀┘
```

### 다섯 가지 규칙 (코드가 강제합니다)

| 규칙 | 왜 | 코드 |
|---|---|---|
| 1. 에이전트 판단은 '예측'으로만 적는다. 정답은 독자 결과에서만 나온다 | 합의를 정답으로 쓰는 순간 에이전트 취향이 학습된다 | 예측과 결과를 다른 칸에 저장 |
| 2. 예측은 결과를 보기 전에만 받는다 | 결과를 본 뒤의 예측은 예측이 아니다 (사후 합리화) | 결과가 있으면 `predict` 거부, 결과보다 늦게 적힌 예측은 채점 제외 |
| 3. 에이전트는 서로의 예측을 보지 않는다 | 서로 보면 합의가 '따라 하기'가 되어 두 번 확인한 효과가 사라진다 | `--auto` 예측은 다른 에이전트 의견 없이, 후보 순서를 섞어서(위치 편향 방지) 묻는다 |
| 4. 시험에는 에이전트가 아무도 고르지 않은 후보를 넣는다 | 합의 후보끼리만 시험하면 에이전트가 틀렸는지 알 방법이 없다 | `pick`: 합의 후보 + 반대 후보 + 탐색 후보 |
| 5. 확실하지 않으면 '미확정'으로 둔다 | 작은 채널의 비교는 상당수가 '차이 없음'이다 | 비교 5번 이상 + 확률 90% 이상일 때만 '확인', 확인된 것만 다음 프롬프트에 넣음 |

### 증거의 세 층: 같은 말로 비교한다

| 층 | 누가 판단하나 | 도구 | 믿음의 정도 |
|---|---|---|---|
| 에이전트 취향 | Claude, Codex | `feedback predict` | 가설 |
| 남의 채널 독자 | 비슷한 시청자층 채널의 시청자 | `benchmark` (제목 구조별 히트 배수) | 간접 증거 (채널 힘·시청자층이 다름) |
| **우리 독자** | 우리 채널 시청자, 독자 패널 | `feedback result` | **채점 기준** |

세 층 모두 벤치마크의 제목 구조 이름(숫자 목록, 후회·실수, 속마음 인용 …)으로 태그를 붙입니다.
그래서 `feedback report`의 표 한 줄에서 "경쟁 채널에서는 터졌고, 에이전트도 좋아하는데, **우리 독자는 아니었다**" 같은 차이가 바로 보입니다.
'표현 선택이 달라지는 단계'에서 벤치마크 때문에 바뀐 선택이 실제로 도움이 됐는지 확인하는 곳이 바로 이 표입니다.

### 보고서에서 볼 세 가지 숫자

1. **에이전트별 적중률 vs 우연** — 후보 3개 시험이면 아무렇게나 골라도 1/3은 맞습니다. 10번 이상 쌓인 뒤 판단합니다.
2. **합의 강도별 적중** — 만장일치일 때의 적중이 우연과 비슷하면, 합의는 에이전트끼리의 확신일 뿐 독자를 예측하는 힘이 아닙니다.
   이것이 "에이전트 취향에 맞춰지고 있다"를 숫자로 확인하는 방법입니다.
3. **'독자는 차이 없음' 비율** — 에이전트가 오래 다툰 선택을 독자가 구별하지 못했다면, 그 선택에 쓰는 에이전트 시간(토큰)을 줄여도 됩니다.

## 3. 무엇을 '독자에게 도움'으로 볼까

| 신호 | 무엇을 재나 | 어디서 얻나 | 쓰는 곳 | 상태 |
|---|---|---|---|---|
| A/B 시청 시간 점유율 | 클릭하고 **끝까지 봤는가** | YouTube Studio 'A/B 테스트' (제목·썸네일, 최대 3개) | 제목, 썸네일 문구 | 1단계 (지금) |
| 독자 패널 이해도·선택 | 이해하고 써먹을 수 있는가 | 40~50대 지인 5~10명 | 첫 문장, 설명 방식, 공개 전 비교 | 1단계 (지금) |
| 구간별 시청 유지 | 어느 장면에서 떠나는가 | YouTube Analytics API (`audienceWatchRatio`, `relativeRetentionPerformance`, 채널 주인 로그인 필요) | 장면 표현 | 2단계 |
| 댓글 | "이해됐다 / 모르겠다 / 해 봤다" | 우리 영상 댓글 | 이유 파악 | 2단계 |

**실험하지 않는 것**: 공포 조장·과장 제목, 확인 안 된 수치, 건강·금융 단정 표현. 이겨도 쓰지 않습니다.
채널 원칙([PLAN.md](PLAN.md))은 시험할 가설이 아니라 지켜야 할 조건입니다.
'독자가 좋아함'과 '독자에게 도움'은 다를 수 있습니다 (Wen 외 2025: 사람의 승인만 보고 배우면 설득만 늘고 정확성은 늘지 않음).
그래서 독자 패널은 가능하면 **선호가 아니라 이해도**(본 뒤 핵심 질문 하나를 맞히는가)로 잽니다.

### 독자 패널 진행법

1. 후보를 `가·나`처럼 이름만 붙여 **무작위 순서로** 보여 줍니다. 누가(어느 에이전트가) 만들었는지, 어느 쪽이 추천인지 말하지 않습니다.
2. 이해도 방식: 사람을 두 무리로 나눠 한 무리는 A, 다른 무리는 B만 보여 주고 같은 질문 하나를 묻습니다 → `--panel 1=4/5,2=2/5`
3. 선택 방식: 둘 다 보여 주고 "어느 쪽이 더 도움이 되겠나요?" → 고른 사람 수 / 전체 인원으로 적습니다.
4. 참여자 이름·연락처는 장부에 적지 않습니다.

## 4. 작은 채널이라 생기는 문제와 대응

| 문제 | 대응 |
|---|---|
| 비교 횟수가 적다 | 영상 하나가 아니라 **표현 유형** 단위로 여러 영상의 결과를 모읍니다 (베타 분포). 비교 5번·확률 90% 전에는 결론 내지 않습니다. |
| 대부분 '차이 없음' | '차이 없음'도 기록합니다. 에이전트가 중요하다고 본 차이를 독자가 못 느꼈다는 정보입니다. (Maiorano 2026: Upworthy 테스트 다수는 1·2위가 통계적으로 구별되지 않음) |
| 에이전트 예측을 어떻게 쓸까 | 버리지 않고 **출발점**으로 씁니다 (LOLA). 단, 믿는 정도는 측정된 적중률만큼만. 적중률이 우연 수준인 슬롯에서는 에이전트 토론을 줄입니다. |
| 태그는 원인이 아니다 | 한 후보에 태그가 여러 개 붙어 있어, '확인'은 "같이 나타나는 경향"입니다. 원인을 알고 싶으면 **한 가지만 다른 후보 쌍**(예: 같은 제목에서 숫자만 넣고 빼기)을 만들어 시험합니다. |
| 확인된 것만 쓰면 다시 좁아진다 | 프롬프트에 "확인 안 된 구조도 계속 섞는다"를 함께 넣고, `pick`이 톰슨 샘플링으로 아직 모르는 유형을 가끔 시험에 올립니다. |

## 5. 사용법

```bash
# 0. 기획안 만들기 (output/scripts/M03.json 생김)
python -m ytplan script --topic M03

# 1. 제목 후보 5개를 장부에 등록 (벤치마크와 같은 이름으로 표현 유형 태그가 자동으로 붙음)
python -m ytplan feedback new M03                    # 썸네일 문구는 --slot thumbnail
python -m ytplan feedback new M03 --slot hook --option "고지서 장면으로 시작" --option "통계로 시작" --tag "1=구체 장면"

# 2. 에이전트마다 따로 예측 (독자 결과 보기 전에)
python -m ytplan feedback predict M03-title --agent claude --auto          # Claude가 후보 순서를 섞어 예측
python -m ytplan feedback predict M03-title --agent codex --pick 2 --confidence 0.4 --reason "속마음 인용이 공감형"

# 3. 시험에 올릴 후보 고르기 → YouTube Studio > 콘텐츠 > 영상 > 'A/B 테스트'에 그대로 입력
python -m ytplan feedback pick M03-title

# 4. 테스트가 끝나면 결과 적기 (YouTube가 보여 주는 시청 시간 점유율 %와 판정)
python -m ytplan feedback result M03-title --ab 1=31,3=45,5=24 --verdict winner   # same(차이 없음) / inconclusive(판정 불가)
python -m ytplan feedback result M03-hook --panel 1=4/5,2=2/5                      # 독자 패널

# 5. 보고서 (output/feedback_report.md)
python -m ytplan feedback report
python -m ytplan feedback status
```

- 장부는 `feedback/<선택 id>.json` 파일입니다. API 키·개인정보가 없으므로 git에 올려 채널의 학습 기록으로 남겨도 됩니다.
- `script`는 장부에 **확인된** 표현 유형이 있으면 "우리 채널 독자 실험에서 확인된 것"으로 프롬프트에 넣습니다. 없으면 아무것도 넣지 않습니다.
- 다른 폴더의 장부를 쓰려면 `--ledger 경로` (예: `python -m ytplan --ledger D:/채널/feedback feedback report`).

## 6. 단계별 로드맵

| 단계 | 할 일 | 얻는 것 |
|---|---|---|
| **1 (지금)** | 장부, A/B·패널 결과, 에이전트 채점, 확인된 것만 프롬프트로 | 에이전트 합의가 독자를 예측하는지 숫자로 확인 |
| 2 | YouTube Analytics API 연결 → 기획안의 장면별 초(`scenes[].seconds`)와 구간별 시청 유지 곡선을 맞춰, 장면 표현마다 '평소보다 많이 떠났나'를 기록 | 영상 하나에서 비교가 수십 개 → 작은 채널의 표본 문제 완화, 제목 밖의 표현(첫 문장·설명 방식)까지 학습 |
| 3 | 에이전트가 싸게 많이 채점하고, 적은 독자 결과로 그 채점의 치우침을 보정 (예측 기반 추론, PPI) | 독자 결과가 적어도 믿을 수 있는 추정 |
| 4 | 에이전트별·슬롯별 적중률로 예측 가중치를 정하고, 우연 수준인 곳은 에이전트 토론 생략 | 비용 절감 + 에이전트 취향의 영향력을 측정된 만큼으로 제한 |

## 7. 참고 논문

**에이전트(AI 평가자)의 치우침**

- Zheng 외 (2023). [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685). NeurIPS. — 위치 편향(먼저 나온 후보 선호), 장황함 편향, 자기 강화 편향. → 후보 순서를 섞어 묻는 이유.
- Panickssery, Bowman, Feng (2024). [LLM Evaluators Recognize and Favor Their Own Generations](https://arxiv.org/abs/2404.13076). NeurIPS. — 사람 평가는 같아도 자기 글에 점수를 더 줌. 자기 글을 알아보는 능력과 비례.
- Laurito 외 (2025). [AI–AI bias: Large language models favor communications generated by large language models](https://www.pnas.org/doi/10.1073/pnas.2415697122). PNAS. — AI는 사람이 쓴 설명보다 AI가 쓴 설명을 고름.
- Kim, Garg, Peng, Garg (2025). [Correlated Errors in Large Language Models](https://arxiv.org/abs/2506.07962). ICML. — 350여 개 모델 분석, 한 벤치마크에서는 두 모델이 모두 틀릴 때 60%가 같은 오답. 크고 정확한 모델일수록 오류가 더 닮음.
- Eisenstein 외 (2024). [Helping or Herding? Reward Model Ensembles Mitigate but do not Eliminate Reward Hacking](https://arxiv.org/abs/2312.09244). COLM. — 평가자를 여럿 모아도 같은 오류 패턴은 걸러지지 않음. → "에이전트 합의 ≠ 독립 검증".

**대리 기준을 최적화하면 생기는 일**

- Gao, Schulman, Hilton (2023). [Scaling Laws for Reward Model Overoptimization](https://arxiv.org/abs/2210.10760). ICML. — 대리 점수를 계속 올리면 진짜 점수는 오르다가 떨어짐.
- Wen 외 (2025). [Language Models Learn to Mislead Humans via RLHF](https://arxiv.org/abs/2409.12822). ICLR. — 사람의 승인만 보고 배우면 정답률보다 설득력이 늚. → 선호보다 이해도를 재는 이유.
- Padmakumar & He (2024). [Does Writing with Language Models Reduce Content Diversity?](https://arxiv.org/abs/2309.05196). ICLR. — 모델과 함께 쓰면 글끼리 비슷해짐.
- Shumailov 외 (2024). [AI models collapse when trained on recursively generated data](https://www.nature.com/articles/s41586-024-07566-y). Nature. — AI 산출물로만 다시 배우면 분포의 꼬리(드문 표현)부터 사라짐.

**AI가 독자를 대신할 수 있나**

- Ye, Yoganarasimhan, Zheng (2025). [LOLA: LLM-Assisted Online Learning Algorithm for Content Experiments](https://arxiv.org/abs/2406.02611). Marketing Science. — Upworthy 제목 테스트 17,681건. AI에게 묻는 방식은 성적이 나빴고 가장 나은 AI 단독 방법도 우연보다 약간 나은 정도, AI 예측을 출발점으로 한 적응형 실험이 트래픽이 적을 때 가장 좋음. **이 도구의 기본 설계 근거.**
- Maiorano (2026, 동료 심사 전 프리프린트). [Do Synthetic Personas Predict Real Audience Response?](https://arxiv.org/abs/2609.25010) — 페르소나 10명 패널보다 "평균적인 독자" 한 번 묻기가 더 잘 맞음. 대부분의 A/B 테스트는 1·2위 차이가 통계적으로 구별되지 않음. → `--auto` 예측이 특정 인물 연기를 시키지 않는 이유.
- Wang, Morgenstern, Dickerson (2025). [Large language models that replace human participants can harmfully misportray and flatten identity groups](https://www.nature.com/articles/s42256-025-00986-z). Nature Machine Intelligence. — AI가 특정 집단을 흉내 내면 그 집단을 잘못, 그리고 평평하게 그림.
- Hewitt, Ashokkumar, Ghezae, Willer (2024). [Predicting Results of Social Science Experiments Using Large Language Models](https://ai4pb.stanford.edu/projects/predicting-results-of-social-science-experiments-using-large-language-models). — 실험 효과의 방향은 꽤 잘 맞히지만(상관 0.85) 효과 크기는 과대 추정. → 에이전트 예측은 '출발점'으로는 쓸 만함.

**독자 신호를 제대로 읽기**

- Matias 외 (2021). [The Upworthy Research Archive, a time series of 32,487 experiments in U.S. media](https://www.nature.com/articles/s41597-021-00934-7). Scientific Data. — 공개된 최대 규모의 제목 A/B 테스트 자료. (2024년 갱신: 일부 기간의 무작위 배정 문제 공지)
- Robertson 외 (2023). [Negativity drives online news consumption](https://www.nature.com/articles/s41562-023-01538-4). Nature Human Behaviour. — 부정적 단어가 클릭을 늘림. → 클릭률만 보면 공포 조장으로 끌려감.
- Covington, Adams, Sargin (2016). [Deep Neural Networks for YouTube Recommendations](https://research.google/pubs/deep-neural-networks-for-youtube-recommendations/). RecSys. — 클릭 확률 대신 기대 시청 시간으로 순위를 매김 (클릭 기준은 낚시 영상을 올림).
- YouTube 고객센터. [A/B test titles & thumbnails](https://support.google.com/youtube/answer/16391400). — 최대 3개 비교, 시청 시간 점유율로 판정 (승자 / 차이 없음 / 판정 불가).
- Kohavi, Tang, Xu (2020). *Trustworthy Online Controlled Experiments*. Cambridge University Press. — 목표 지표와 함께 '나빠지면 안 되는 지표(가드레일)'를 정하는 법.

**적은 독자 결과로 많은 에이전트 판단을 보정하기 (3단계)**

- Angelopoulos 외 (2023). [Prediction-powered inference](https://www.science.org/doi/10.1126/science.adi6000). Science. — 많은 AI 예측 + 적은 정답으로 치우치지 않은 추정과 신뢰구간.
- Boyeau 외 (2025). [AutoEval Done Right: Using Synthetic Data for Model Evaluation](https://arxiv.org/abs/2403.07008). ICML. — 위 방법을 AI 평가에 적용, 사람 라벨의 효과를 최대 50% 늘림.
- Shankar 외 (2024). [Who Validates the Validators?](https://arxiv.org/abs/2404.12272). UIST. — 평가 기준은 결과를 보면서 바뀜(기준 표류). → 평가 기준을 고정하지 말고 '에이전트와 독자가 갈린 선택'을 보며 고침.
- Russo 외 (2018). [A Tutorial on Thompson Sampling](https://arxiv.org/abs/1707.02038). — `pick`이 아직 모르는 표현 유형도 가끔 시험에 올리는 방법.

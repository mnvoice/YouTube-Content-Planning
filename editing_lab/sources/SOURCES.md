# 읽은 범위와 확인하지 못한 범위 (2026-09-30 준비 단계)

## 인수인계와 기존 기록

| 대상 | 결과 | 이유 |
|---|---|---|
| `/Users/jeong-ujin_1/Documents/Obsidian Vault/NLP_공부/짧은글_편집실험_인수인계_2026-09-30_002.md` | **읽지 못함** (SHA-256 없음) | 사용자 Mac의 경로. 이 작업은 클라우드 컨테이너에서 실행되어 해당 경로가 없음 |
| 인수인계와 연결된 기존 논문 검토 자료 | **읽지 못함** | 같은 이유. 파일 목록도 알 수 없음 |
| Google Drive 검색 (`인수인계`, `편집실험`, `짧은글`, `SummEval`, `Flower`, `Self-Refine`, `NLP_공부`) | 결과 없음 | 드라이브에 동기화된 사본 없음 |
| 사용자 컴퓨터에 연결된 Claude 세션 | 없음 | 메시지를 보낼 수 있는 세션이 없음 |

## 논문 원문

네트워크 정책이 막은 호스트 (프록시 403): `aclanthology.org`, `arxiv.org`, `export.arxiv.org`, `proceedings.neurips.cc`, `www.jstor.org`,
`direct.mit.edu`, `nlp.cs.berkeley.edu`, `openai.com`, `www.researchgate.net`, `openreview.net`, `www.semanticscholar.org`, `api.semanticscholar.org`, `selfrefine.info`.
따라서 **다섯 논문 모두 본문 PDF를 읽지 못했다.** 확인은 저자 공식 저장소 자료(1차)와 웹 검색 요약(2차)으로 했다.

| 논문 | 실제로 읽은 것 | SHA-256 (받은 사본) | 확인하지 못한 것 |
|---|---|---|---|
| Flower & Hayes (1981) | 웹 검색 요약만 (2차) | — | 논문 본문 전체, 모형 그림, 사고 구술 자료 |
| DOC, Yang 외 (2023) | 저자 저장소 README `raw.githubusercontent.com/yangkevin2/doc-story-generation/main/README.md`, 웹 검색 초록 | `bf6250b875bbf00f3ec01bfe49704cf08b3dad5da9af275013c6e28efc8f0ef7` | 논문 본문, 인간 평가 절차 세부 |
| SummEval, Fabbri 외 (2021) | 저자 저장소 README `raw.githubusercontent.com/Yale-LILY/SummEval/master/README.md`, 웹 검색 요약 | `5de6b266c252b00c722d33d6745c45647bf6512f993f2137637547e60c7df474` | 논문 본문, 평가 지침 원문 전체 |
| Self-Refine, Madaan 외 (2023) | 저자 저장소 README와 프로젝트 페이지 소스 `raw.githubusercontent.com/madaan/self-refine/main/{README.md, docs/index.html}` | README `54f667a07214567976b2966fcb87ce881afdc1aeb745ce07d1f139ae8747882a`, 프로젝트 페이지 `3c64633e641d767bfa241787c3f48925d48fe9257de5d8e1eaa078465381bec1` | 논문 본문, 막연한 피드백 대 구체적 피드백 비교 수치 |
| Stiennon 외 (2020) | 저자 저장소 README `raw.githubusercontent.com/openai/summarize-from-feedback/master/README.md`, 웹 검색 요약 | `5c5c30159193e8d5d104fa0aeda27cbfdee1ba7053ca43807cc7d59b5af917d0` | 논문 본문, 과최적화 그래프 수치, 평가자 일치율 |

받은 README 사본은 저장소에 싣지 않았다 (각 저장소의 저작물). 위 URL과 SHA-256으로 같은 파일인지 다시 확인할 수 있다.
각 검토 에이전트가 추가로 읽은 자료는 `criteria/reviewer_*_criteria.md` 끝에 에이전트가 직접 적었다.

## 막힌 것을 푸는 방법

1. **인수인계 문서**: 사용자 컴퓨터에서 실행되는 Claude 세션(Claude 데스크톱 앱, 또는 해당 폴더에서 `claude remote-control`)에서 읽거나,
   문서 내용을 이 대화에 붙여 넣으면 된다. 읽은 뒤 SHA-256을 작업 기록에 추가한다.
2. **논문 원문**: 이 클라우드 환경의 네트워크 설정(세션 제목 표시줄의 환경 메뉴 → Edit → Network access)에서
   `aclanthology.org`, `arxiv.org`, `proceedings.neurips.cc`를 허용 도메인에 추가하면 DOC·SummEval·Self-Refine·Stiennon 본문을 읽을 수 있다.
   Flower & Hayes (1981)는 JSTOR 유료 논문이라 사용자가 가진 PDF를 받아야 한다.

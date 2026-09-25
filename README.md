# YouTube 콘텐츠 기획 도구: 40~50대 '정보 + 공감' 채널

40~50대 시청자를 위한 AI 제작 유튜브 채널을 기획하는 문서와 도구입니다.

- **무엇을 만들까**: 7개 콘텐츠 기둥, 45개 검증 후보 아이템 → [docs/PLAN.md](docs/PLAN.md)
- **소재를 어떻게 구할까**: 발견 → 검증 → 확정 방법과 매주 루틴 → [docs/SOURCING.md](docs/SOURCING.md)
- **AI로 어떻게 만들까**: 제작 흐름, 화면 가독성, YouTube·국내 정책 → [docs/PRODUCTION.md](docs/PRODUCTION.md)
- **자동화 도구 `ytplan`**: 아이템 조사 → 점수 → 캘린더 → 대본 생성 (아래)
- **바로 보는 결과 예시** (API 키 없이 만든 것): [순위표](examples/ranking.md) · [2026년 10~12월 업로드 캘린더](examples/calendar.md) · [M03 기획 프롬프트](examples/scripts/M03_prompt.md)

## 도구가 하는 일

```
 topic_bank.csv          research                 rank / calendar           script
 (아이템 45개,     →   유튜브 아웃라이어·댓글   →   점수표와              →   Claude가 제목·썸네일·
  엑셀로 편집)          네이버 데이터랩(40~50대)      업로드 일정               장면별 대본·이미지 프롬프트·
                        최근 뉴스                                              사실 확인 목록 작성
```

| 명령 | 하는 일 | 필요한 키 |
|---|---|---|
| `bank` | 아이템 뱅크 보기 | 없음 |
| `expand "키워드"` | 유튜브 자동완성으로 연관 검색어 모으기 | 없음 |
| `research` | 유튜브 인기·아웃라이어 영상, 사연·질문 댓글, 40~50대 검색량, 최근 뉴스 조사 | YouTube, 네이버 (없으면 뉴스만) |
| `rank` | 점수 매겨 순위표 만들기 | 없음 (조사 결과가 있으면 반영) |
| `calendar` | 기둥을 섞고 시즌을 맞춘 업로드 일정 | 없음 |
| `script` | 영상 기획안(대본) 생성 | Anthropic (없으면 `--prompt-only`) |

## 빠른 시작

Python 3.10 이상이 필요합니다.

```bash
git clone https://github.com/mnvoice/YouTube-Content-Planning.git
cd YouTube-Content-Planning
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 키 없이 바로 해 볼 수 있는 것
python -m ytplan bank -v                           # 아이템 45개 자세히 보기
python -m ytplan expand "퇴직 후 건강보험"          # 사람들이 실제로 치는 검색어
python -m ytplan rank                              # 순위표 → output/ranking.md
python -m ytplan calendar --weeks 12 --days 화,금   # 12주 일정 → output/calendar.md
python -m ytplan script --topic M03 --prompt-only  # claude.ai에 붙여 넣을 프롬프트
```

## API 키 넣기

`.env.example`을 `.env`로 복사한 뒤 값을 채웁니다. `.env`는 git에 올라가지 않습니다.

| 키 | 발급처 | 비용·한도 |
|---|---|---|
| `YOUTUBE_API_KEY` | [Google Cloud 콘솔](https://console.cloud.google.com/) → 프로젝트 생성 → 'YouTube Data API v3' 사용 설정 → 사용자 인증 정보 → API 키 | 무료, 하루 10,000 유닛 (아이템 1개 조사에 약 105 유닛 → 하루 약 90개) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | [네이버 개발자센터](https://developers.naver.com/apps/) → 애플리케이션 등록 → 사용 API '데이터랩(검색어트렌드)' | 무료, 하루 1,000회 |
| `ANTHROPIC_API_KEY` | [Claude Console](https://console.anthropic.com/) | 유료 (사용량 과금) |

키를 넣은 뒤:

```bash
python -m ytplan research --pillar 돈      # 돈·노후 기둥 전체 조사
python -m ytplan research --topic M03,H02  # 특정 아이템만
python -m ytplan rank                      # 이제 검색수요·아웃라이어가 반영됨
python -m ytplan script --topic M03        # output/scripts/M03.md
```

- 조사 결과는 `research/<ID>.json`(원본)과 `output/research/<ID>.md`(읽기용)로 저장됩니다.
- 같은 요청은 24시간 동안 `.cache/`에서 재사용해 할당량을 아낍니다.
- 기획안은 Claude(`claude-opus-5`)로 만들고, 안전 분류기가 요청을 거절하면 서버가 권장 모델로 자동 재시도(`fallbacks: "default"`)하도록 켜 두었습니다.

## 아이템 추가·수정

`ytplan/data/topic_bank.csv`를 엑셀이나 구글 시트로 열어 행을 추가하면 됩니다.

| 칸 | 설명 |
|---|---|
| `id` | 기둥 머리글자 + 번호 (H=건강, M=돈·노후, W=일, F=가족, P=마음, L=생활, N=추억) |
| `empathy_hook` | 시청자가 속으로 하는 말. 영상 첫 문장이 됩니다 |
| `info_core` | 전달할 핵심 정보 |
| `sources` | 사실 확인할 공식 출처 (`;`로 구분) |
| `keywords` | 검색·트렌드 조회용 키워드, 첫 번째가 대표 (`;`로 구분) |
| `season` | 올리기 좋은 달 (`1;12`) 또는 `all`. 행사·제도 시점보다 조금 앞선 달로 적기 |
| `empathy`, `info`, `ai_fit` | 1~5점 |
| `risk` | `low` / `med` / `high` (건강·금융처럼 틀리면 피해가 큰 주제일수록 높게) |

## 폴더 구조

```
docs/                 기획 문서 (전략, 소재 발굴, 제작·정책)
ytplan/
  data/topic_bank.csv 아이템 뱅크
  sources/            youtube.py · naver.py · news.py
  research.py         조사 실행·저장
  scoring.py          점수 모델
  planner.py          업로드 캘린더
  generate.py         Claude 기획안 생성
  cli.py              명령줄 도구
tests/                pytest 테스트 (네트워크 없이 실행)
```

## 테스트

```bash
pip install pytest
python -m pytest
```

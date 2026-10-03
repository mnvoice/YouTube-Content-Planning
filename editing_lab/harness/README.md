# 기록 하네스 (1.1판)

받은 원본(1판, 사용자 설명상 코덱스 작성): `../handoff/2026-10-03_harness/` (수정 금지, manifest에 SHA-256).
명령과 저장 구조는 원본 README(`../handoff/2026-10-03_harness/extracted/README.md`)와 같다. 1.1판에서 바뀐 점만 여기에 적는다.

## 완료 판정

- 기준: `ACCEPTANCE.md` (기준표 1판). 이 표로만 완료를 판정한다(U13).
- 측정: `python3 editing_lab/harness/acceptance.py --harness <경로> --label <이름> --save`
- 실제 사례 재생: `python3 editing_lab/harness/replay.py --harness <경로>`
- 결과: `results/` (날짜와 판별로 새 파일, 덮어쓰지 않음)
- 회귀 감시: `tests/test_harness_acceptance.py` (1단계 기준과 유지 기준)

## 1.1판에서 바뀐 점 (1단계)

| 바뀐 곳 | 1판 | 1.1판 | 관련 기준 |
|---|---|---|---|
| 원문 사본 | 글로 읽고 다시 써서 CRLF·CR이 LF로 바뀜 | 바이트 그대로 복사 | A1 |
| 후보 해시와 저장 | 줄바꿈을 바꾼 글로 해시를 잼. `shasum`으로 잰 CRLF 파일을 거부 | 파일 바이트로 해시를 재고 바이트 그대로 저장 | A2 |
| 되돌리기 뒤 단계 | 과거 스냅샷의 단계를 그대로 써서, 이미 받은 검토·반론과 어긋나 사례가 막힘 | 저장된 검토·반론·후보에서 단계를 다시 계산 | D1, D2 |
| 판 표시 | 없음 | 상태에 `harness_version: "1.1"` | — |

바꾸지 않은 것: 의미 판정 규칙(U3와 다름), 반응의 필수 칸, 보류 기록의 내용, 창작 분기, 단계 종류. 이것들은 2·3단계 대상이다(`ACCEPTANCE.md` 2절).

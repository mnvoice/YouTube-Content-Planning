# 실행 담당(Codex)용 벤치마크 실행·검증 절차

분석과 기획은 Claude, 로컬 실행과 산출물 검증은 Codex가 맡는 경우의 절차입니다.
`<HASH>`는 사용자에게 전달받은 커밋 해시, `<ORIGINAL>`은 기존 설치 폴더 경로입니다.

## 지킬 것

- **기존 설치 폴더, 그 안의 `.env`, 기존 결과는 건드리지 않습니다.** `.env`는 `--env-file`로 **읽기만** 합니다.
- 새 작업 폴더에서 `<HASH>` 커밋을 그대로 실행합니다. 코드를 고치지 않습니다. (고치면 검증에서 '수정 파일 있음'으로 실패)
- `setup`은 반드시 `--check`와 함께만 씁니다. `--check` 없이 쓰면 키 파일을 수정합니다.
- `ideas --append`는 쓰지 않습니다. (아이템 뱅크를 바꿈)
- 결과 폴더의 파일은 수정하지 않습니다. 수정하면 SHA-256이 달라져 전달 확인이 안 됩니다.
- 결과는 GitHub에 올리지 않습니다. `.env`와 `.cache/`는 전달하지 않습니다.

## 1. 새 작업 폴더에 지정 커밋 받기

```bash
git clone https://github.com/mnvoice/YouTube-Content-Planning.git ytplan-run
cd ytplan-run
git checkout <HASH>          # 'detached HEAD' 안내가 나오는 게 정상
git rev-parse HEAD           # <HASH>와 같은지 확인
```

## 2. 설치와 테스트

```bash
python -m venv .venv
.venv\Scripts\activate       # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q          # 모두 passed 여야 함 (네트워크·할당량 사용 없음)
```

## 3. 키 연결 확인 (원본 `.env` 읽기만, 할당량 1 유닛)

```bash
python -m ytplan --env-file "<ORIGINAL>/.env" setup --check --only youtube
```

`[정상] YouTube: 정상`이 나와야 합니다.

## 4. 벤치마크 실행 (할당량 약 1,150 유닛, 몇 분)

```bash
python -m ytplan --env-file "<ORIGINAL>/.env" benchmark
```

- 결과는 새 폴더 `output/benchmark_날짜-시간/`에 생깁니다. 이미 있는 폴더에는 쓰지 않습니다.
- 파일: `benchmark.json`(원자료 포함 전체), `benchmark.md`(보고서), `channels.csv`(채널별 상태), `run.log`(실행 기록)
- 할당량이 중간에 바닥나면 그때까지의 결과를 저장하고 `meta.complete = false`로 표시합니다.
  이 경우 다음 날(한국 시간 오후 4~5시 이후) **같은 작업 폴더에서** 다시 실행하면 24시간 캐시 덕분에 할당량을 덜 씁니다.

## 5. 검증

```bash
python -m ytplan verify-run output/benchmark_날짜-시간 --expect-commit <HASH>
```

통과하면 종료 코드 0, 하나라도 실패하면 1입니다. 결과는 같은 폴더의 `verification.md`에 저장됩니다.

| 검증 항목 | 확인 내용 |
|---|---|
| 필수 파일 | 4개 파일이 모두 있는가 |
| 코드 커밋 | 실행 코드가 `<HASH>`이고 수정 파일이 없는가 |
| 실행 완료 | 할당량 소진 등으로 중간에 멈추지 않았는가 (멈췄다면 부분 결과) |
| 수집 건수 일치 | 전체 = 성공 + 보류 + 실패 + 미실행, 채널별 상태와 합계가 맞는가 |
| 채널 상태 일치 | 실패·미실행 채널이 계산에 섞이지 않았는가 |
| 평소 조회수·배수 재계산 | 저장된 원자료로 다시 계산한 중앙값·배수가 보고서와 같은가 |
| 히트 재계산 | 기준(2배·1만 회)으로 다시 뽑은 히트 목록이 같은가, 모두 '성공' 채널에서 나왔는가 |
| 제목 구조 재계산 | 제목 구조별 건수가 같은가 |
| channels.csv 행 수 / 보고서 숫자 일치 | 표·보고서가 JSON과 같은 숫자를 쓰는가 |
| API 키 노출 없음 | 결과 파일 어디에도 키가 없는가 |

## 6. 사용자에게 보고할 것

1. 실행 커밋 해시와 `pytest` 결과 (예: `90 passed`)
2. `verify-run` 결과표 (`verification.md` 그대로)
3. 수집 건수: 전체·성공·보류·실패·미실행 (`benchmark.md` 1장)
4. 빠진 채널과 영향: 계산에서 빠진 채널, 그 채널들의 비중, 분석된 채널이 없는 시드 (`benchmark.md` 1장 '빠진 채널과 영향')
5. 할당량 사용 추정치 (`benchmark.md` 0장)

## 7. 전달할 파일

`output/benchmark_날짜-시간/` 안의 5개 파일을 **수정하지 않은 채로** 전달합니다.

- `benchmark.json`, `benchmark.md`, `channels.csv`, `run.log`, `verification.md`

받는 쪽은 `verification.md`에 적힌 SHA-256과 받은 파일의 SHA-256을 비교해 같은 파일인지 확인합니다.

```bash
# Windows PowerShell
Get-FileHash output\benchmark_날짜-시간\benchmark.json -Algorithm SHA256
# macOS/Linux
shasum -a 256 output/benchmark_날짜-시간/benchmark.json
```

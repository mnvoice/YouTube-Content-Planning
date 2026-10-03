# 짧은 글 편집 기록 하네스

작성일: 2026-10-03

하는 일: 원문 → 독립 검토 3개 → 반론 3개 → 변경안 → 사용자 반응을 연결합니다.
역할: Python 표준 라이브러리로 입력, 단계, 파일 지문과 실행 기록을 관리합니다.

## 실행 방법

Python 3.9 이상이 필요합니다. 아래 명령은 이 폴더에서 실행합니다. 원문 경로와 JSON 파일 경로는 실제 자료로 바꿉니다. examples의 내용은 양식이며 실제 평가 결과가 아닙니다.

```sh
python3 harness.py --case cases/example init --source /absolute/path/original.md --goal '귀에 잘 들어오는 이야기' --scope same_content
python3 harness.py --case cases/example review --role purpose --input examples/review_purpose.json
python3 harness.py --case cases/example review --role structure --input examples/review_structure.json
python3 harness.py --case cases/example review --role meaning --input examples/review_meaning.json
python3 harness.py --case cases/example object --role purpose --input examples/object_purpose.json
python3 harness.py --case cases/example object --role structure --input examples/object_structure.json
python3 harness.py --case cases/example object --role meaning --input examples/object_meaning.json
python3 harness.py --case cases/example candidate --input /absolute/path/candidate.md --decision examples/decision.json
python3 harness.py --case cases/example feedback --input examples/feedback.json
python3 harness.py --case cases/example verify
python3 harness.py --case cases/example report
python3 harness.py --case cases/example rollback --snapshot 8
```

candidate 등록 전에 decision.json을 실제 선택 근거와 최종 문자열의 의미 검토 결과로 채웁니다. SHA-256은 `shasum -a 256 /absolute/path/candidate.md`로 계산할 수 있습니다. same_content는 preserved 판정만 받으며 creative는 changed와 uncertain도 표시하여 받습니다. 이 판정은 제출자의 검토 결과이며 프로그램이 의미 보존을 증명하지 않습니다.

## 저장 구조

- original.md: 원문 복사본. 지문으로 변경을 확인합니다.
- state_000001.json 등: 사건마다 생성하는 새 상태 스냅샷.
- events.jsonl: 성공한 실행의 시간순 기록.
- held.jsonl: 잘못된 형식이나 단계 등 보류 사유.
- review 및 object JSON: 역할별 원본 응답.
- candidate Markdown, decision JSON, diff TXT: 변경안, 선택 근거, 줄 단위 실제 대조.
- feedback JSON: 실제 사용자 반응.
- config_v1.json: 역할, 모델 식별 정보와 반복 한도.

문장 내부의 변화는 diff 줄 전체에서 확인합니다. 자동 글자 단위 시각화는 포함하지 않습니다. 파일 손상이 감지되면 후속 실행을 중단하고 보류 사유를 남깁니다. JSONL과 여러 파일을 묶는 작업은 데이터베이스 트랜잭션이 아니므로 중간 장애 때 디렉터리를 점검해야 합니다. 동시에 여러 프로세스로 한 사례를 수정하지 않습니다.

## 구현 범위

외부 모델 호출, 벡터 DB, 자동 지시문 개선과 자동 채택은 구현하지 않습니다. 세션에서 실제 검토를 수행한 후 JSON을 가져오는 기록 하네스입니다. 이야기 지도는 review JSON의 story_map에 수록할 수 있으나 현재 강제 검증 대상은 제안 계약입니다. 사례 검색은 폴더와 JSON을 대상으로 할 수 있으며 검색 명령은 별도 구현하지 않았습니다.

rollback은 후보 선택과 설정 버전을 과거 상태로 복원하고 새 사건을 남깁니다. 기존 결과와 반응을 삭제하지 않으며 이미 사용한 후보 한도를 초기화하지 않습니다. 현재 설정 버전은 v1 하나이므로 지시문 개선 비교와 승격은 후속 구현이 필요합니다. 모델의 동일 출력 재현을 보장하지 않습니다.

## 검증

```sh
python3 -m unittest -v test_harness.py
```

테스트는 임시 폴더의 합성 글과 합성 검토로 실행합니다. 실제 글쓰기 실험이나 독자 평가를 수행하지 않습니다.

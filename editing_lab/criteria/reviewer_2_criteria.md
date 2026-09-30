<!-- 작성: 에이전트 2(생성된 검토 에이전트), 2026-09-30. 진행자는 머리말 줄만 붙였고 본문은 에이전트가 돌려준 그대로 저장함. -->

# 에이전트 2 기준 카드: DOC (Yang, Klein, Peng, Tian, ACL 2023). 논문 원문은 확인하지 못함.
(코드에서 읽은 동작은 저자 공식 자료이므로 `[논문 직접]`으로 표시함. 다만 논문 본문과 같게 서술됐는지는 확인하지 못함.)

기준 1. 필수 사실 목록을 '개요'로, 원문을 '본문'으로 나눈다. 문장을 옮긴 뒤에도 개요 항목마다 대응하는 구절이 하나씩 남아 있는지 먼저 맞춰 본다. `[응용 판단]`
 출처: 계획(위계 개요)과 초안(개요를 따르게 제어)을 나눈다는 점은 `[논문 직접]` README에서 확인함("We first generate the plan/outline before moving on to the main story", 세부 제어기를 끄면 "worse faithfulness to the plan/outline"). alignment_loader.py는 다른 위치의 본문을 해당 요약과 짝지은 것을 부정 예시로 씀. 초록은 WebSearch 요약(2차 자료)으로만 봄.
 검사 질문: 옮긴 뒤에도 필수 사실 각각이 몇 번째 문장에 있는지 다시 짚을 수 있는가?

기준 2. 옮긴 문장은 앞부분 전체와 뒷부분 전체 사이에 끼워 넣었을 때 제자리로 읽히는지로 판정한다. `[응용 판단]`
 출처: `[논문 직접]` 저자 코드. order_loader.py는 한 문장을 다른 위치에 넣은 글을 0, 원래 위치의 글을 1로 두고 학습함. outline.py 395–402행은 후보 항목을 *로 표시해 앞(prefix)과 뒤(suffix) 사이에 넣고 순서 점수로 정렬함.
 검사 질문: 옮긴 문장을 가리고 앞뒤만 읽었을 때 그 자리에 그 문장이 오리라고 예상되는가?

기준 3. 앞당긴 문장이 뒤에 나올 사실을 미리 담아 버리지(선취) 않는지, 늦춘 문장이 이미 말한 내용을 되풀이하게 되지 않는지 둘 다 본다. `[응용 판단]`
 출처: `[논문 직접]` 저자 코드. outline.py 361–375행은 새 개요 항목이 앞 항목에 함의되면(확률 0.5 초과) 버리고, 뒤 항목을 함의해도 버림. fine_coherence_loader.py 131–138행은 세부 제어기의 부정 예시로 'repeat'(이미 쓴 문장)와 'shuffle'(뒤에 올 문장)을 씀. 한편 beam_candidate.py 174행은 다음 개요 항목을 프롬프트에 넣음. 다음 내용을 알고 쓰되 미리 말하지는 않게 하는 구조임.
 검사 질문: 이동 뒤 어떤 사실이 처음 나오는 문장이 바뀌었는가? 그 때문에 뒤 문장이 새 정보 없이 되풀이만 하게 되었는가?

기준 4. 인물·대상·장소 정보는 그 지점까지 드러난 것만 전제한다. 지시어·대명사·생략된 주어가 가리키는 대상보다 먼저 나오지 않는지, 시간·장소 전환이 표시되는지 본다. `[응용 판단]`
 출처: `[논문 직접]` 저자 코드. entity.py 343–365행(get_outline_description_up_to_node)은 현재 개요 지점까지의 인물 설명만 쓰고, 첫 등장이면 "first appearance"를 붙임. beam_candidate.py 189행은 장면이 바뀌면 "initially takes place in X … then move to Y"라고 밝혀 적음.
 검사 질문: 옮긴 문장 속 '그/이것/생략된 주어'가 가리킬 대상이 이미 앞에 나왔는가?

기준 5. 공개를 늦추면 궁금증이 커진다는 기대는 효과가 아니라 예상으로만 적는다. 혼란과 오해의 가능성도 같은 무게로 적는다. `[미검증 예상]`
 출처: Re3 대비 흥미도 +20.7% 등은 WebSearch 요약(2차 자료)임. 이는 시스템 전체를 비교한 결과이고, 공개 시점을 조작한 효과가 아님.
 검사 질문: 늦춘 사실을 기다리는 동안 독자가 원인·조건·대상을 잘못 가정하게 되는 문장은 어느 것인가?

## 확인하지 못한 범위
- 논문 PDF 전체(방법 절, 인간 평가 설계와 문항, 절제 실험, 부록)는 원문을 확인하지 못함. 수치와 초록은 WebSearch 요약으로만 봄.
- 코드는 일부 파일의 일부만 읽음. plan.py, FUDGE 제어기 구현, 학습 데이터 CSV, v2 저장소(facebookresearch/doc-storygen-v2)는 읽지 않음. 코드 동작과 논문 서술이 일치하는지 맞춰 보지 못함.
- 함의 임계값 0.5와 순서 재정렬기 학습 데이터(README: "very brief, outline-like stories")가 논문 본문에 어떻게 서술됐는지 확인하지 못함.

## 이 관점의 한계
- DOC는 영어 장편(평균 3500단어 이상)을 자동 생성하는 시스템이다. 문장 위치나 공개 시점을 독립 변수로 두고 독자 반응을 잰 실험이 아니다. 그래서 짧은 글에서 어떤 배치가 더 이해하기 쉬운지는 말할 수 없다.
- 순서 재정렬기는 원래 순서를 정답으로 삼아 학습했다. 그래서 '제자리가 아니다'를 잡는 발상은 주지만, '옮긴 쪽이 더 낫다'의 근거는 되지 못한다. 판단이 원문 순서 쪽으로 기울 수 있다.
- 반복과 선취를 거르는 규칙은 장편 줄거리의 일관성을 위한 것이다. 짧은 설명글에서는 두괄식, 요약 되풀이, 의도적 복선이 이해를 돕기도 하는데, 이 규칙으로 보면 모두 벌점 대상이다. 두괄식과 미괄식 중 무엇이 나은지는 이 관점으로 판단할 수 없다.
- 짧은 글의 개요는 한두 단계뿐이라 계층 제어의 이점이 거의 옮겨오지 않을 수 있다. 위치를 옮길 때 한국어 조사·어미·접속어가 바뀌는 문제는 전혀 다루지 않는다.

## 역할 지시문에서 고칠 점
1. '실제 순서'가 시간 순서인지 논리적 선후인지가 설명글·주장글에서는 어긋날 수 있다. 진행자가 사례를 시작할 때 둘 중 하나를 정해 주기를 제안한다.
2. 지시 대상보다 앞으로 문장을 옮기면 대명사를 명사로 바꾸거나(그→○○) 문장을 나눠야 할 때가 있다. 지금 예외는 '조사·접속어 한두 개'뿐이라 지시어 교체나 문장 분할이 허용되는지 불분명하다.

실제로 읽은 것: [파일] editing_lab/roles/common_rules.md, editing_lab/roles/reviewer_2_order.md, scratchpad/papers/doc_README.md · [URL, 앞부분 raw.githubusercontent.com/yangkevin2/doc-story-generation/main/] story_generation/common/controller/loaders/order_loader.py(전체), alignment_loader.py(전체), fine_coherence_loader.py(전체), story_generation/plan_module/outline.py(270–435행 정독, 나머지는 grep), story_generation/draft_module/beam_candidate.py(126–200행 정독, 나머지는 grep), story_generation/edit_module/entity.py(343–392행), scripts/main.py(grep만). plan.py·name_util.py·common/util.py·summarizer_util.py는 존재 여부(HTTP 200)만 확인하고 읽지 않음. api.github.com 트리 조회는 거부됨. 차단된 호스트(arxiv, aclanthology, nlp.cs.berkeley.edu)에는 접속하지 않음 · [WebSearch 검색어] "DOC Improving Long Story Coherence With Detailed Outline Control Yang Klein Peng Tian abstract detailed outliner detailed controller" / "DOC detailed outliner "entailment" filtering outline items order reranker Yang 2023 story generation"

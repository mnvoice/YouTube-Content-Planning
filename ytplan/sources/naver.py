"""네이버 데이터랩 검색어 트렌드로 '40~50대가 실제로 검색하는 양'을 비교한다.

네이버 데이터랩 API는 연령대 필터를 지원해서 40~59세만 따로 볼 수 있다는 점이 핵심이다.
(https://developers.naver.com 에서 애플리케이션 등록 → '데이터랩(검색어트렌드)' 선택)

주의: 결과의 ratio는 '한 번의 요청 안에서 가장 큰 값을 100으로 둔 상대값'이다.
요청 하나에 키워드 그룹이 최대 5개라서, 많은 아이템을 비교하려면
모든 요청에 같은 기준 키워드(anchor)를 넣고 그 값을 100으로 맞춰 이어 붙인다.
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import net

URL = "https://openapi.naver.com/v1/datalab/search"
# 연령 코드: 7=40~44, 8=45~49, 9=50~54, 10=55~59
AGES_40_50 = ["7", "8", "9", "10"]
DEFAULT_ANCHOR = ("국민연금",)  # 40~50대 관심이 꾸준한 기준 키워드
MAX_GROUPS = 5
MAX_KEYWORDS_PER_GROUP = 20


def search_trend(
    client_id: str,
    client_secret: str,
    groups: dict[str, list[str]],
    start: date,
    end: date,
    ages: list[str] = AGES_40_50,
    gender: str = "",
    time_unit: str = "week",
) -> dict[str, list[float]]:
    """키워드 그룹별 기간 ratio 목록을 돌려준다."""
    if not 1 <= len(groups) <= MAX_GROUPS:
        raise ValueError(f"키워드 그룹은 1~{MAX_GROUPS}개여야 합니다")
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": time_unit,
        "keywordGroups": [
            {"groupName": name, "keywords": kws[:MAX_KEYWORDS_PER_GROUP]} for name, kws in groups.items()
        ],
        "ages": ages,
    }
    if gender:
        body["gender"] = gender
    data = net.post_json(
        URL,
        body,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/json",
        },
    )
    return {r["title"]: [float(p["ratio"]) for p in r.get("data", [])] for r in data.get("results", [])}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def momentum(series: list[float], recent: int = 4, base: int = 12) -> float | None:
    """최근 {recent}주 평균 ÷ 그 이전 {base}주 평균. 1보다 크면 관심이 오르는 중."""
    if len(series) < recent + base:
        return None
    prev = _mean(series[-(recent + base) : -recent])
    if prev <= 0:
        return None
    return round(_mean(series[-recent:]) / prev, 2)


def compare_topics(
    client_id: str,
    client_secret: str,
    topics: dict[str, list[str]],
    weeks: int = 52,
    anchor: tuple[str, ...] = DEFAULT_ANCHOR,
    gender: str = "",
    today: date | None = None,
) -> dict[str, dict]:
    """여러 아이템의 40~50대 검색 수요를 기준 키워드 대비 배수로 비교한다.

    반환값의 demand는 '기준 키워드 평균 검색량을 1로 봤을 때의 배수'다.
    """
    end = today or date.today()
    start = end - timedelta(weeks=weeks)
    anchor_name = "__anchor__"
    ids = list(topics)
    per_batch = MAX_GROUPS - 1
    results: dict[str, dict] = {}
    for i in range(0, len(ids), per_batch):
        batch = ids[i : i + per_batch]
        groups = {anchor_name: list(anchor)}
        groups.update({tid: topics[tid] for tid in batch})
        series = search_trend(client_id, client_secret, groups, start, end, gender=gender)
        anchor_mean = _mean(series.get(anchor_name, []))
        for tid in batch:
            s = series.get(tid, [])
            results[tid] = {
                "demand": round(_mean(s) / anchor_mean, 3) if anchor_mean > 0 else None,
                "momentum": momentum(s),
                "anchor": " / ".join(anchor),
                "weeks": weeks,
            }
    return results

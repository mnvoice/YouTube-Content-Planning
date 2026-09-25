"""최근 뉴스로 아이템의 '시의성'을 확인한다 (구글 뉴스 RSS, API 키 불필요).

제도 변경·통계 발표가 있는 달에는 같은 주제라도 조회수가 크게 오른다.
단, 뉴스는 소재 발견용이다. 영상에 쓰는 수치는 반드시 1차 출처(공단·부처 발표)로 확인한다.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .. import net

RSS_URL = "https://news.google.com/rss/search"


def parse_rss(xml_text: str, limit: int = 10) -> dict:
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    parsed = []
    for item in items[:limit]:
        source = item.find("source")
        parsed.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "source": source.text.strip() if source is not None and source.text else "",
            }
        )
    return {"count": len(items), "items": parsed}


def recent_news(query: str, days: int = 30, limit: int = 10) -> dict:
    """최근 {days}일 기사 수(최대 100)와 상위 헤드라인."""
    text = net.get_text(
        RSS_URL,
        {"q": f"{query} when:{days}d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        ttl=6 * 3600,
    )
    result = parse_rss(text, limit=limit)
    result.update({"query": query, "days": days})
    return result

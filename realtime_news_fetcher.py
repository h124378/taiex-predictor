"""
realtime_news_fetcher.py
------------------------
隨時更新全球與台股重大財經即時新聞
來源包含：
1. 鉅亨網 (Anue Cnyes) 即時頭條新聞 API
2. Google 財經台灣與國際即時新聞 RSS

提供自動分類標籤 (如：聯準會/升降息、AI/半導體、地緣政治、外資籌碼等) 與多空風向評估
"""

import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

# 台灣時區 UTC+8
TZ_TW = timezone(timedelta(hours=8))

class NewsItem:
    def __init__(self, title: str, source: str, link: str, published_time: str, summary: str = "", tags: list = None, sentiment: str = "中立"):
        self.title = title
        self.source = source
        self.link = link
        self.published_time = published_time
        self.summary = summary
        self.tags = tags or []
        self.sentiment = sentiment  # 利多, 利空, 中立

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "link": self.link,
            "published_time": self.published_time,
            "summary": self.summary,
            "tags": self.tags,
            "sentiment": self.sentiment
        }


def analyze_news_sentiment_and_tags(title: str, summary: str = "") -> tuple[str, list[str]]:
    """依據標題與內文進行關鍵字規則分析多空與分類標籤"""
    text = f"{title} {summary}".lower()
    
    tags = []
    bullish_score = 0
    bearish_score = 0

    # 標籤辨識
    tag_keywords = {
        "AI/半導體": ["ai", "半導體", "晶圓", "台積電", "輝達", "nvidia", "tsmc", "asml", "超微", "amd", "先進封裝", "co-wos", "伺服器", "字節跳動"],
        "Fed/央行利率": ["fed", "聯準會", "降息", "升息", "鮑爾", "利率", "非農", "cpi", "通膨", "殖利率", "國債"],
        "外資/籌碼": ["外資", "投信", "三大法人", "自營商", "買超", "賣超", "庫存", "軋空"],
        "國際政經": ["關稅", "川普", "白宮", "拜登", "地緣", "烏克蘭", "中東", "制裁", "貿易"],
        "科技巨頭": ["蘋果", "apple", "微軟", "google", "meta", "特斯拉", "tesla", "亞馬遜", "amazon"],
        "原油/原物料": ["原油", "石油", "金價", "黃金", "銅價", "opec"]
    }

    for tag, kws in tag_keywords.items():
        if any(kw in text for kw in kws):
            tags.append(tag)

    if not tags:
        tags.append("即時總經焦點")

    # 多空評估
    bullish_keywords = ["大漲", "暴漲", "狂飆", "創高", "大買", "買超", "噴發", "利多", "超預期", "強勁", "豪取", "飆升", "大賺", "加碼", "突破"]
    bearish_keywords = ["大跌", "重挫", "暴跌", "雪崩", "大賣", "賣超", "利空", "低於預期", "疲軟", "狂瀉", "警告", "警訊", "衰退", "破底"]

    for kw in bullish_keywords:
        if kw in text:
            bullish_score += 1
    for kw in bearish_keywords:
        if kw in text:
            bearish_score += 1

    if bullish_score > bearish_score:
        sentiment = "利多"
    elif bearish_score > bullish_score:
        sentiment = "利空"
    else:
        sentiment = "中立"

    return sentiment, tags[:3]


def fetch_cnyes_headlines(limit: int = 8) -> List[NewsItem]:
    """獲取鉅亨網即時重大焦點頭條"""
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/headline?limit={limit}"
    items = []
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if res.status_code == 200:
            data = res.json().get("items", {}).get("data", [])
            for row in data:
                title = row.get("title", "").strip()
                news_id = row.get("newsId")
                link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else "https://news.cnyes.com"
                pub_ts = row.get("publishAt")
                
                if pub_ts:
                    dt = datetime.fromtimestamp(pub_ts, tz=TZ_TW)
                    pub_str = dt.strftime("%H:%M")
                else:
                    pub_str = datetime.now(TZ_TW).strftime("%H:%M")
                
                summary = row.get("summary", "") or ""
                sentiment, tags = analyze_news_sentiment_and_tags(title, summary)
                items.append(NewsItem(
                    title=title,
                    source="鉅亨網",
                    link=link,
                    published_time=pub_str,
                    summary=summary[:120] if summary else "",
                    tags=tags,
                    sentiment=sentiment
                ))
    except Exception as e:
        pass
    return items


def fetch_google_tw_finance_news(limit: int = 8) -> List[NewsItem]:
    """獲取 Google 台灣財經重大焦點 RSS"""
    url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            raw_items = root.findall("./channel/item")
            for it in raw_items[:limit]:
                full_title = it.find("title").text or ""
                if " - " in full_title:
                    parts = full_title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                else:
                    title = full_title.strip()
                    source = "即時財經"

                link = it.find("link").text or ""
                pub_date_str = it.find("pubDate").text or ""
                pub_str = ""
                try:
                    dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                    dt_tw = dt.replace(tzinfo=timezone.utc).astimezone(TZ_TW)
                    pub_str = dt_tw.strftime("%H:%M")
                except Exception:
                    pub_str = datetime.now(TZ_TW).strftime("%H:%M")

                sentiment, tags = analyze_news_sentiment_and_tags(title)
                items.append(NewsItem(
                    title=title,
                    source=source,
                    link=link,
                    published_time=pub_str,
                    summary="",
                    tags=tags,
                    sentiment=sentiment
                ))
    except Exception as e:
        pass
    return items


_NEWS_CACHE = {
    "data": [],
    "last_fetched": 0.0
}

def get_latest_financial_news(force_refresh: bool = False, max_count: int = 10) -> List[NewsItem]:
    """獲取即時財經新聞，具備 60 秒內部快取"""
    current_time = time.time()
    if not force_refresh and _NEWS_CACHE["data"] and (current_time - _NEWS_CACHE["last_fetched"] < 60):
        return _NEWS_CACHE["data"][:max_count]

    cnyes_news = fetch_cnyes_headlines(limit=7)
    google_news = fetch_google_tw_finance_news(limit=7)

    combined = []
    seen_titles = set()

    for item in cnyes_news + google_news:
        simple_title = "".join(ch for ch in item.title if ch.isalnum())[:12]
        if simple_title and simple_title not in seen_titles:
            seen_titles.add(simple_title)
            combined.append(item)

    if combined:
        _NEWS_CACHE["data"] = combined
        _NEWS_CACHE["last_fetched"] = current_time

    return _NEWS_CACHE["data"][:max_count]

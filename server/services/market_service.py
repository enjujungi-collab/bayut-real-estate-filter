"""
PropertyFinder API 기반 시장 분석 — 임대 수익률, 가격 추이
"""
import os
import asyncio
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://propertyfinder-uae-data.p.rapidapi.com"

DEFAULT_YIELDS = {
    "Apartment": {0: 7.2, 1: 6.5, 2: 5.8, 3: 5.2, 4: 4.8},
    "Villa":      {3: 4.8, 4: 4.5, 5: 4.0},
    "Townhouse":  {3: 5.0, 4: 4.7},
    "Penthouse":  {3: 4.5, 4: 4.2},
}


def _headers() -> dict:
    return {
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY", ""),
        "x-rapidapi-host": "propertyfinder-uae-data.p.rapidapi.com",
        "User-Agent": "RapidAPI/4.0",
    }


async def _fetch_rent_avg(location_id: int, bedrooms: Optional[int]) -> Optional[float]:
    """평균 연간 임대료 조회"""
    params = {"location_id": location_id, "transaction_type": "rented"}
    if bedrooms is not None:
        params["bedrooms"] = bedrooms
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}/get-transactions",
                                    params=params, headers=_headers())
            if resp.status_code != 200:
                return None
            data = resp.json()
            summary = (data.get("data", {}).get("data", {})
                       .get("attributes", {}).get("summary", {}))
            avg = summary.get("rent_new_avg_price") or summary.get("rent_renew_avg_price")
            return float(avg) if avg else None
    except Exception:
        return None


async def _fetch_price_trend(location_id: int, bedrooms: Optional[int]) -> list[dict]:
    """월별 sqft당 가격 추이 (1Y)"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}/price-trend-of-location",
                                    params={"location_id": location_id}, headers=_headers())
            if resp.status_code != 200:
                return []
            data = resp.json()
            # Try multiple nesting paths the API might return
            attrs = (data.get("data", {}).get("data", {}).get("attributes", {})
                     or data.get("data", {}).get("attributes", {})
                     or data.get("attributes", {}))
            graph = attrs.get("graph", {}).get("1Y", []) or attrs.get("graph", [])
            if not graph:
                return []

            # bedroom_id may be int or string in API response
            bed_id = bedrooms if bedrooms is not None else 2
            filtered = [g for g in graph
                        if g.get("bedroom_id") == bed_id
                        or str(g.get("bedroom_id", "")) == str(bed_id)]
            if not filtered:
                filtered = graph  # fallback: use all bedroom types

            # community_price may have different field names
            result = []
            for g in filtered:
                val = (g.get("community_price") or g.get("median_price")
                       or g.get("avg_price") or g.get("price"))
                period = g.get("period") or g.get("month") or g.get("date")
                if val and period:
                    result.append({"period": str(period), "value": float(val)})
            # deduplicate by period, keep latest value
            seen = {}
            for r in result:
                seen[r["period"]] = r["value"]
            return [{"period": k, "value": v} for k, v in list(seen.items())[:12]]
    except Exception:
        return []


_MARKET_TEXTS = {
    "ko": {
        "trend": lambda loc, cat, pct, dir_: f"{loc} {cat} 시장은 최근 1년간 ft²당 가격이 {pct:.1f}% {dir_}했습니다.",
        "up": "상승", "down": "하락",
        "underval": lambda d: f"이 매물은 시장 평균 대비 약 AED {d:,.0f} 저평가된 것으로 분석됩니다.",
        "overval":  lambda d: f"이 매물은 시장 평균 대비 약 AED {d:,.0f} 고평가된 것으로 분석됩니다.",
        "atval": "이 매물은 현재 시장 평균에 부합하는 가격대입니다.",
        "yield_ctx": lambda y, avg, comp: f"예상 임대 수익률 {y}%는 두바이 평균({avg}%)을 {comp}합니다.",
        "above": "상회", "below": "하회",
        "default": "시장 데이터를 분석 중입니다.",
    },
    "en": {
        "trend": lambda loc, cat, pct, dir_: f"The {loc} {cat} market has seen a {pct:.1f}% {dir_} in price per ft² over the past year.",
        "up": "increase", "down": "decrease",
        "underval": lambda d: f"This property is estimated to be approximately AED {d:,.0f} below market value.",
        "overval":  lambda d: f"This property is estimated to be approximately AED {d:,.0f} above market value.",
        "atval": "This property is priced in line with the current market average.",
        "yield_ctx": lambda y, avg, comp: f"The projected rental yield of {y}% is {comp} the Dubai average ({avg}%).",
        "above": "above", "below": "below",
        "default": "Analyzing market data.",
    },
    "zh": {
        "trend": lambda loc, cat, pct, dir_: f"{loc} {cat}市场过去一年每平方英尺价格{dir_} {pct:.1f}%。",
        "up": "上涨", "down": "下跌",
        "underval": lambda d: f"该房产估计低于市场均价约 AED {d:,.0f}。",
        "overval":  lambda d: f"该房产估计高于市场均价约 AED {d:,.0f}。",
        "atval": "该房产定价与当前市场均价相符。",
        "yield_ctx": lambda y, avg, comp: f"预计租金回报率 {y}% {comp}迪拜平均水平（{avg}%）。",
        "above": "高于", "below": "低于",
        "default": "正在分析市场数据。",
    },
    "ar": {
        "trend": lambda loc, cat, pct, dir_: f"شهد سوق {cat} في {loc} {dir_} بنسبة {pct:.1f}٪ في السعر لكل قدم مربع خلال العام الماضي.",
        "up": "ارتفاعاً", "down": "انخفاضاً",
        "underval": lambda d: f"يُقدَّر أن هذا العقار أقل من متوسط السوق بحوالي AED {d:,.0f}.",
        "overval":  lambda d: f"يُقدَّر أن هذا العقار أعلى من متوسط السوق بحوالي AED {d:,.0f}.",
        "atval": "يتوافق سعر هذا العقار مع متوسط السوق الحالي.",
        "yield_ctx": lambda y, avg, comp: f"العائد الإيجاري المتوقع {y}٪ {comp} متوسط دبي ({avg}٪).",
        "above": "يتجاوز", "below": "أقل من",
        "default": "جاري تحليل بيانات السوق.",
    },
}

async def get_market_data(
    location_id: int,
    location_name: str,
    category: str,
    bedrooms: Optional[int],
    area_sqft: Optional[float],
    sale_price: int,
    lang: str = "ko",
) -> dict:
    rent_avg, price_history = await asyncio.gather(
        _fetch_rent_avg(location_id, bedrooms),
        _fetch_price_trend(location_id, bedrooms),
    )

    # 임대 수익률
    rental_yield_pct = None
    if rent_avg and sale_price > 0:
        rental_yield_pct = round((rent_avg / sale_price) * 100, 1)
    else:
        beds_key = bedrooms if bedrooms is not None else 1
        yield_table = DEFAULT_YIELDS.get(category, DEFAULT_YIELDS["Apartment"])
        rental_yield_pct = yield_table.get(
            beds_key,
            yield_table.get(min(yield_table.keys(), key=lambda k: abs(k - beds_key)), 5.5)
        )

    # 추정 시세 (최신 sqft 가격 × 면적)
    estimated_value = None
    if price_history and area_sqft:
        latest_psf = price_history[-1]["value"]
        estimated_value = round(latest_psf * area_sqft / 1000) * 1000

    # 시장 코멘트
    MT = _MARKET_TEXTS.get(lang, _MARKET_TEXTS["en"])
    context_parts = []
    if len(price_history) >= 3:
        first_val = price_history[0]["value"]
        last_val  = price_history[-1]["value"]
        change = ((last_val - first_val) / first_val) * 100
        direction = MT["up"] if change > 0 else MT["down"]
        context_parts.append(MT["trend"](location_name, category, abs(change), direction))
    if estimated_value and sale_price:
        diff = estimated_value - sale_price
        if diff > 50_000:
            context_parts.append(MT["underval"](diff))
        elif diff < -50_000:
            context_parts.append(MT["overval"](abs(diff)))
        else:
            context_parts.append(MT["atval"])
    if rental_yield_pct:
        avg = 5.0
        comp = MT["above"] if rental_yield_pct > avg else MT["below"]
        context_parts.append(MT["yield_ctx"](rental_yield_pct, avg, comp))

    market_context = " ".join(context_parts) or MT["default"]

    return {
        "estimated_value":  estimated_value,
        "rental_yield_pct": rental_yield_pct,
        "price_history":    price_history,
        "market_context":   market_context,
    }

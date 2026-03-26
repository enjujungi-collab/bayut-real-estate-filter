import os
import httpx
from typing import Optional
from dotenv import load_dotenv
from .models import Property, SearchFilters

load_dotenv()

BASE_URL = "https://uae-real-estate2.p.rapidapi.com"


def _get_headers() -> dict:
    key = os.getenv("RAPIDAPI_KEY")
    if not key or key == "your_rapidapi_key_here":
        raise ValueError(
            "RAPIDAPI_KEY가 설정되지 않았습니다.\n"
            ".env 파일에 RAPIDAPI_KEY=<your_key> 를 추가해주세요.\n"
            "키 발급: https://rapidapi.com → 'bayut' 검색 → 구독"
        )
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "uae-real-estate2.p.rapidapi.com",
        "Content-Type": "application/json",
    }


def search_locations(query: str) -> list[dict]:
    """위치 이름으로 location_id 조회 (자동완성)"""
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            f"{BASE_URL}/locations_search",
            params={"query": query, "langs": "en"},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        # 결과 형태: [{"id": 5, "name": "Dubai", "slug": "dubai", ...}, ...]
        return data if isinstance(data, list) else data.get("results", [])


def search_properties(filters: SearchFilters, page: int = 0) -> tuple[list[Property], int]:
    """매물 검색. (결과 목록, 전체 개수) 반환"""
    payload = filters.to_api_payload()

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{BASE_URL}/properties_search",
            params={"page": page, "langs": "en"},
            json=payload,
            headers=_get_headers(),
        )
        _handle_errors(resp)
        data = resp.json()

    hits = data.get("hits", data) if isinstance(data, dict) else data
    total = data.get("nbHits", len(hits)) if isinstance(data, dict) else len(hits)

    properties = [_parse_property(h) for h in hits]
    return properties, total


def get_property_detail(property_id: str) -> Optional[Property]:
    """단일 매물 상세 정보 조회"""
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            f"{BASE_URL}/property_info",
            params={"id": property_id, "langs": "en"},
            headers=_get_headers(),
        )
        _handle_errors(resp)
        data = resp.json()

    if not data:
        return None
    return _parse_property(data)


def _handle_errors(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise ValueError("API 인증 실패: RAPIDAPI_KEY를 확인해주세요.")
    if resp.status_code == 429:
        raise RuntimeError("API 요청 한도 초과 (Rate limit). 잠시 후 다시 시도해주세요.")
    resp.raise_for_status()


def _parse_property(data: dict) -> Property:
    location_parts = []
    for key in ("district", "city", "country"):
        val = data.get(key, {})
        if isinstance(val, dict):
            name = val.get("name_en") or val.get("name") or ""
        else:
            name = str(val) if val else ""
        if name:
            location_parts.append(name)
    location = ", ".join(location_parts) or data.get("location", "-")

    # ── URL: slug 그대로 사용, 없으면 id 기반 fallback ──────────
    slug = (data.get("slug") or "").strip().strip("/")
    if slug:
        # slug가 이미 .html 포함 여부와 무관하게 깔끔하게 조합
        url = f"https://www.bayut.com/{slug}"
        if not url.endswith(".html") and not url.endswith("/"):
            url += "/"
    else:
        url = f"https://www.bayut.com/property/details-{data.get('id', '')}.html"

    # ── 이미지 URL 수집 ──────────────────────────────────────────
    photos = []
    for raw in data.get("photos", []):
        if isinstance(raw, dict):
            img_url = (raw.get("url") or raw.get("main") or raw.get("thumbnail") or "")
        else:
            img_url = str(raw)
        img_url = img_url.strip()
        if img_url and img_url.startswith("http"):
            photos.append(img_url)

    # ── 에이전트 연락처 ──────────────────────────────────────────
    agent = data.get("agent", {}) if isinstance(data.get("agent"), dict) else {}
    agency = data.get("agency", {}) if isinstance(data.get("agency"), dict) else {}
    phone = agent.get("phone") or agent.get("mobile") or agent.get("phone_number") or ""

    return Property(
        id=str(data.get("id", "")),
        title=data.get("title_en") or data.get("title") or "-",
        purpose=data.get("purpose", "-"),
        category=data.get("category", {}).get("name_en", "-") if isinstance(data.get("category"), dict) else str(data.get("category", "-")),
        location=location,
        price=int(data.get("price", 0) or 0),
        currency=data.get("currency", "AED"),
        bedrooms=data.get("rooms"),
        bathrooms=data.get("baths"),
        area_sqft=data.get("area"),
        is_completed=data.get("is_completed"),
        url=url,
        agent_name=agent.get("name") or None,
        agency_name=agency.get("name_en") or agency.get("name") or None,
        agent_phone=phone or None,
        amenities=[a.get("name", "") for a in data.get("amenities", []) if isinstance(a, dict)],
        photos=photos[:5],
        description=data.get("description_en") or data.get("description") or None,
        floor=data.get("floor_number") or data.get("floor") or None,
        total_floors=data.get("total_floors") or None,
        furnishing=data.get("furnishing") or None,
        permit_number=data.get("permit_number") or data.get("reference_number") or None,
    )

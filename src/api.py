import os
import httpx
from typing import Optional
from dotenv import load_dotenv
from .models import Property, SearchFilters

load_dotenv()

BASE_URL = "https://propertyfinder-uae-data.p.rapidapi.com"


def _get_headers() -> dict:
    key = os.getenv("RAPIDAPI_KEY")
    if not key or key == "your_rapidapi_key_here":
        raise ValueError(
            "RAPIDAPI_KEY가 설정되지 않았습니다.\n"
            ".env 파일에 RAPIDAPI_KEY=<your_key> 를 추가해주세요."
        )
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "propertyfinder-uae-data.p.rapidapi.com",
        "User-Agent": "RapidAPI/4.0",
    }


def search_locations(query: str) -> list[dict]:
    """위치 이름으로 location_id 조회"""
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            f"{BASE_URL}/autocomplete-location",
            params={"query": query},
            headers=_get_headers(),
        )
        _handle_errors(resp)
        data = resp.json()
        return data.get("data", [])


def search_properties(filters: SearchFilters, page: int = 0) -> tuple[list[Property], int]:
    """매물 검색. (결과 목록, 전체 개수) 반환"""
    endpoint = "/search-buy" if filters.purpose == "for-sale" else "/search-rent"

    params = {"page": page + 1}

    # 위치
    if filters.locations_ids:
        params["location_id"] = str(filters.locations_ids[0])

    # 가격
    if filters.price_min:
        params["price_min"] = filters.price_min
    if filters.price_max:
        params["price_max"] = filters.price_max

    # 방 개수
    if filters.rooms and len(filters.rooms) == 1:
        params["bedrooms"] = filters.rooms[0]

    # 면적 (sqft → sqm 변환: PropertyFinder는 sqft 사용)
    if filters.area_min:
        params["size_min"] = filters.area_min
    if filters.area_max:
        params["size_max"] = filters.area_max

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            headers=_get_headers(),
        )
        _handle_errors(resp)
        data = resp.json()

    props_raw = data.get("data", [])
    if not isinstance(props_raw, list):
        props_raw = []

    # 활성 매물 + 가격 있는 것만 필터
    props_raw = [p for p in props_raw
                 if p.get("is_available", True)
                 and (p.get("price", {}) or {}).get("value", 0) > 0]

    total = len(props_raw)
    properties = [_parse_property(p, filters.purpose) for p in props_raw]
    return properties, total


def get_property_detail(property_id: str) -> Optional[Property]:
    """단일 매물 상세 정보 조회"""
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            f"{BASE_URL}/property-details",
            params={"property_id": property_id},
            headers=_get_headers(),
        )
        _handle_errors(resp)
        data = resp.json()

    prop = data.get("data")
    if not prop:
        return None
    if isinstance(prop, list):
        prop = prop[0] if prop else None
    if not prop:
        return None
    return _parse_property(prop, "for-sale")


def _handle_errors(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise ValueError("API 인증 실패: RAPIDAPI_KEY를 확인해주세요.")
    if resp.status_code == 429:
        raise RuntimeError("API 요청 한도 초과 (Rate limit). 잠시 후 다시 시도해주세요.")
    resp.raise_for_status()


def _parse_property(data: dict, purpose: str = "for-sale") -> Property:
    # 위치
    addr = data.get("address", {}) or {}
    location = addr.get("full_name", "-")

    # URL — property_url 필드 직접 사용 (항상 유효한 PropertyFinder 링크)
    url = data.get("property_url", "")
    if not url:
        prop_id = data.get("property_id", "")
        url = f"https://www.propertyfinder.ae/en/search?q={prop_id}"

    # 이미지
    photos = [img for img in (data.get("images") or []) if img][:5]

    # 에이전트
    agent_info = data.get("agent_details", {}) or {}
    agent_name = agent_info.get("name") or data.get("agent_name") or None

    # 가격
    price_info = data.get("price", {}) or {}
    if isinstance(price_info, dict):
        price = int(price_info.get("value") or 0)
        currency = price_info.get("currency", "AED")
    else:
        price = int(price_info or 0)
        currency = "AED"

    # 방/욕실/면적
    bedrooms_raw = data.get("bedrooms")
    try:
        bedrooms = int(bedrooms_raw) if bedrooms_raw is not None else None
    except (ValueError, TypeError):
        bedrooms = None

    bathrooms_raw = data.get("bathrooms")
    try:
        bathrooms = int(bathrooms_raw) if bathrooms_raw is not None else None
    except (ValueError, TypeError):
        bathrooms = None

    size_raw = data.get("size")
    try:
        area_sqft = round(float(size_raw)) if size_raw else None
    except (ValueError, TypeError):
        area_sqft = None

    # 제목/설명/카테고리
    title = data.get("title") or location or "-"
    description = data.get("description")
    category = data.get("property_type", "Apartment")

    # 완공 여부
    is_new = data.get("is_new_construction")
    is_completed = not is_new if is_new is not None else None

    return Property(
        id=str(data.get("property_id") or ""),
        title=title,
        purpose=purpose,
        category=category,
        location=location,
        price=price,
        currency=currency,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_sqft=area_sqft,
        is_completed=is_completed,
        url=url,
        agent_name=agent_name,
        agency_name=None,
        agent_phone=None,
        amenities=[],
        photos=photos,
        description=description,
        floor=None,
        total_floors=None,
        furnishing=None,
        permit_number=data.get("reference_number"),
    )

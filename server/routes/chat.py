from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys, os, asyncio, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.api import search_locations, search_properties
from src.models import SearchFilters
from server.services.claude_service import parse_query

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. Claude로 필터 파싱
    result = await parse_query(req.message, req.history)
    if result["filters"] is None:
        return {"reply": result["reply"], "properties": [], "filters": None}

    raw = result["filters"]

    # 2. 위치 ID 조회 (rate limit 방지: 재시도 포함)
    location_ids = []
    location_name = raw.get("location_name", "")
    if location_name:
        for attempt in range(3):
            try:
                locs = search_locations(location_name)
                if locs:
                    location_ids = [locs[0]["id"]]
                    location_name = locs[0].get("name") or location_name
                break
            except RuntimeError:   # rate limit
                await asyncio.sleep(1.5 * (attempt + 1))
            except Exception:
                break

    # rate limit 방지: 위치 조회와 매물 검색 사이 딜레이
    await asyncio.sleep(1.0)

    # 3. SearchFilters 구성
    filters = SearchFilters(
        purpose=raw.get("purpose", "for-sale"),
        categories=raw.get("categories", ["apartments"]),
        locations_ids=location_ids,
        location_name=location_name,
        price_min=raw.get("price_min"),
        price_max=raw.get("price_max"),
        rooms=raw.get("rooms"),
        area_min=raw.get("area_min"),
        area_max=raw.get("area_max"),
        is_completed=raw.get("is_completed"),
        sort_by=raw.get("sort_by", "popular"),
    )

    # 4. 매물 검색 (최대 6개, rate limit 재시도 포함)
    for attempt in range(3):
        try:
            properties, total = search_properties(filters, page=0)
            break
        except RuntimeError:   # rate limit
            if attempt == 2:
                raise HTTPException(status_code=429, detail="rate_limit")
            await asyncio.sleep(2.0 * (attempt + 1))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail="api_error")

    properties = properties[:25]

    # 5. 응답 직렬화
    def serialize(p):
        return {
            "id": p.id, "title": p.title, "purpose": p.purpose,
            "category": p.category, "location": p.location,
            "price": p.price, "currency": p.currency,
            "price_formatted": p.price_formatted,
            "bedrooms": p.bedrooms, "bedrooms_label": p.bedrooms_label,
            "bathrooms": p.bathrooms, "area_sqft": p.area_sqft,
            "area_formatted": p.area_formatted,
            "is_completed": p.is_completed, "url": p.url,
            "photos": p.photos, "amenities": p.amenities,
            "agent_name": p.agent_name, "agency_name": p.agency_name,
            "agent_phone": p.agent_phone,
            "description": p.description,
            "floor": p.floor, "total_floors": p.total_floors,
            "furnishing": p.furnishing, "permit_number": p.permit_number,
        }

    return {
        "reply": result["reply"],
        "language": result.get("language", "ko"),
        "filters": {
            "purpose": filters.purpose,
            "categories": filters.categories,
            "location_name": filters.location_name,
            "locations_ids": filters.locations_ids,
            "price_min": filters.price_min,
            "price_max": filters.price_max,
            "rooms": filters.rooms,
            "sort_by": filters.sort_by,
        },
        "properties": [serialize(p) for p in properties],
        "total": total,
    }

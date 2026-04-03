import asyncio
import tempfile
import os
import sys
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from src.api import get_property_detail, search_locations
from src.models import SearchFilters
from server.services.market_service import get_market_data
from server.services.map_service import fetch_map_image
from server.pdf_builder import build_portfolio_pdf

router = APIRouter()


class PdfRequest(BaseModel):
    properties: list[dict]
    filters: Optional[dict] = None
    language: str = "ko"


@router.post("/api/pdf")
async def generate_pdf(req: PdfRequest):
    if not req.properties:
        raise HTTPException(status_code=400, detail="매물이 없습니다.")

    filters_dict = req.filters or {}
    location_name = filters_dict.get("location_name", "UAE")
    locations_ids = filters_dict.get("locations_ids", [])
    location_id   = locations_ids[0] if locations_ids else None

    filters = SearchFilters(
        purpose=filters_dict.get("purpose", "for-sale"),
        categories=filters_dict.get("categories", ["apartments"]),
        location_name=location_name,
        locations_ids=locations_ids,
        price_min=filters_dict.get("price_min"),
        price_max=filters_dict.get("price_max"),
        rooms=filters_dict.get("rooms"),
    )

    # 각 매물의 상세 + 시장 데이터 + 지도를 병렬로 조회
    async def enrich(p_dict: dict) -> dict:
        prop_id = p_dict.get("id", "")
        # 상세 정보 재조회 (더 많은 이미지)
        try:
            detail = await asyncio.to_thread(get_property_detail, prop_id)
        except Exception:
            detail = None

        # 상세 조회 결과 병합
        if detail:
            p_dict["photos"]      = detail.photos or p_dict.get("photos", [])
            p_dict["description"] = detail.description or p_dict.get("description")
            p_dict["amenities"]   = detail.amenities or p_dict.get("amenities", [])
            p_dict["floor"]       = detail.floor or p_dict.get("floor")
            p_dict["total_floors"]= detail.total_floors or p_dict.get("total_floors")
            p_dict["furnishing"]  = detail.furnishing or p_dict.get("furnishing")
            p_dict["permit_number"]= detail.permit_number or p_dict.get("permit_number")

        # 시장 데이터 (location_id 있을 때만)
        market = {"estimated_value": None, "rental_yield_pct": None,
                  "price_history": [], "market_context": ""}
        if location_id:
            try:
                market = await get_market_data(
                    location_id=location_id,
                    location_name=location_name,
                    category=(p_dict.get("category") or "apartments"),
                    bedrooms=p_dict.get("bedrooms"),
                    area_sqft=p_dict.get("area_sqft"),
                    sale_price=p_dict.get("price", 0),
                    lang=req.language,
                    purpose=(p_dict.get("purpose") or filters_dict.get("purpose", "for-sale")),
                )
            except Exception:
                pass
        p_dict["market"] = market

        # 지도 이미지 — 좁은 범위부터 넓은 범위로 fallback 시도
        map_bytes = None
        try:
            raw_loc = p_dict.get("location") or location_name
            parts = [p.strip() for p in raw_loc.split(",") if p.strip()]
            # 시도 순서: 마지막 2개 → 마지막 1개(도시) → "Dubai"
            queries = []
            if len(parts) >= 2:
                queries.append(", ".join(parts[-2:]))
            if parts:
                queries.append(parts[-1])
            queries.append("Dubai")
            for q in queries:
                map_bytes = await fetch_map_image(q)
                if map_bytes:
                    break
        except Exception:
            pass
        p_dict["map_bytes"] = map_bytes

        return p_dict

    enriched = await asyncio.gather(*[enrich(dict(p)) for p in req.properties])

    # PDF 생성 — 64MB 스택 스레드에서 실행 (ReportLab 레이아웃 엔진 스택 초과 방지)
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        def _run():
            try:
                build_portfolio_pdf(list(enriched), filters, tmp_path, req.language)
                loop.call_soon_threadsafe(future.set_result, None)
            except Exception as exc:
                import traceback; traceback.print_exc()
                loop.call_soon_threadsafe(future.set_exception, exc)

        old_size = threading.stack_size(64 * 1024 * 1024)   # 64 MB
        t = threading.Thread(target=_run, daemon=True)
        threading.stack_size(old_size or 0)
        t.start()
        await future

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 생성 오류: {e}")

    from datetime import datetime
    filename = f"bayut_portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return FileResponse(
        tmp_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

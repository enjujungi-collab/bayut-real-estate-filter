"""
OpenStreetMap 기반 정적 지도 이미지 생성 (무료, API 키 불필요)
"""
import io
import asyncio
import httpx
from typing import Optional

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "BayutPortfolioApp/1.0 (real-estate-filter)"}


async def geocode(location: str) -> Optional[tuple[float, float]]:
    """위치 문자열 → (lat, lon)"""
    params = {"q": f"{location}, UAE", "format": "json", "limit": 1}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=HEADERS)
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


async def fetch_map_image(location: str, width: int = 400, height: int = 280,
                          zoom: int = 14) -> Optional[bytes]:
    """위치 문자열 → PNG bytes (실패 시 None)"""
    coords = await geocode(location)
    if coords is None:
        return None
    lat, lon = coords

    def _render():
        from staticmap import StaticMap, CircleMarker
        m = StaticMap(width, height,
                      url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        marker = CircleMarker((lon, lat), "#E8A838", 14)
        m.add_marker(marker)
        image = m.render(zoom=zoom, center=[lon, lat])
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    try:
        return await asyncio.to_thread(_render)
    except Exception:
        return None

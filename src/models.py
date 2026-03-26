from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Property:
    id: str
    title: str
    purpose: str          # for-sale / for-rent
    category: str         # apartment, villa, etc.
    location: str
    price: int
    currency: str
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    area_sqft: Optional[float]
    is_completed: Optional[bool]
    url: str
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    agent_phone: Optional[str] = None
    amenities: list = field(default_factory=list)
    photos: list = field(default_factory=list)          # 이미지 URL 목록
    description: Optional[str] = None                   # 매물 설명
    floor: Optional[int] = None                         # 층수
    total_floors: Optional[int] = None
    furnishing: Optional[str] = None                    # 가구 여부
    permit_number: Optional[str] = None                 # 등록 번호

    @property
    def price_formatted(self) -> str:
        if self.price >= 1_000_000:
            return f"{self.price / 1_000_000:.2f}M {self.currency}"
        elif self.price >= 1_000:
            return f"{self.price / 1_000:.0f}K {self.currency}"
        return f"{self.price:,} {self.currency}"

    @property
    def bedrooms_label(self) -> str:
        if self.bedrooms is None:
            return "-"
        if self.bedrooms == 0:
            return "Studio"
        return f"{self.bedrooms}BR"

    @property
    def area_formatted(self) -> str:
        if self.area_sqft is None:
            return "-"
        return f"{self.area_sqft:,.0f} ft²"


@dataclass
class SearchFilters:
    purpose: str = "for-sale"
    categories: list = field(default_factory=lambda: ["apartments"])
    locations_ids: list = field(default_factory=list)
    location_name: str = ""
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    rooms: Optional[list] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    is_completed: Optional[bool] = None
    sort_by: str = "popular"

    def to_api_payload(self) -> dict:
        payload: dict = {
            "purpose": self.purpose,
            "categories": self.categories,
            "index": self.sort_by,
        }
        if self.locations_ids:
            payload["locations_ids"] = self.locations_ids
        if self.price_min is not None:
            payload["price_min"] = self.price_min
        if self.price_max is not None:
            payload["price_max"] = self.price_max
        if self.rooms:
            payload["rooms"] = self.rooms
        if self.area_min is not None:
            payload["area_min"] = self.area_min
        if self.area_max is not None:
            payload["area_max"] = self.area_max
        if self.is_completed is not None:
            payload["is_completed"] = self.is_completed
        return payload

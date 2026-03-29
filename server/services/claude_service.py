"""
Claude API를 이용해 자연어 쿼리를 Bayut 검색 필터로 변환
"""
import os
import json
import asyncio
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client: Optional[anthropic.Anthropic] = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY가 .env에 설정되지 않았습니다.")
        _client = anthropic.Anthropic(api_key=key)
    return _client


SYSTEM_PROMPT = """You are a real estate search assistant for UAE properties on Bayut.com.
Convert the user's natural language request into structured search filters.

Rules:
- purpose: "for-sale" if user says buy/purchase/invest/매매/구매. "for-rent" if rent/lease/임대/렌트. Default: "for-sale".
- categories: one of [apartments, villas, townhouses, penthouses, studios, offices, retail].
  flat/unit/아파트 → apartments. house/빌라/villa → villas. studio/스튜디오 → studios. Default: apartments.
- Prices are in AED unless stated. Convert "1M"→1000000, "500k"→500000, "100만"→1000000, "50만"→500000.
- rooms: integer list. studio/스튜디오 → [0]. "2BR/2베드/2침실" → [2]. Multiple: "2 or 3" → [2,3].
- location_name: extract the location string in English (e.g. "Dubai Marina", "Palm Jumeirah", "Downtown Dubai").
- sort_by: default "popular". cheapest/lowest → "lowest_price". newest → "latest". most expensive → "highest_price".
- is_completed: true if "ready/completed/완공", false if "off-plan/분양중". Otherwise null.
- If unclear, make a reasonable assumption and proceed — do not ask for clarification.
- Always use the search_properties tool, never respond with plain text only."""


TOOLS = [
    {
        "name": "search_properties",
        "description": "Search Bayut UAE real estate with structured filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purpose":       {"type": "string", "enum": ["for-sale", "for-rent"]},
                "categories":    {"type": "array", "items": {"type": "string",
                                  "enum": ["apartments","villas","townhouses",
                                           "penthouses","studios","offices","retail"]}},
                "location_name": {"type": "string", "description": "Location in English"},
                "price_min":     {"type": ["integer","null"]},
                "price_max":     {"type": ["integer","null"]},
                "rooms":         {"type": ["array","null"], "items": {"type": "integer"}},
                "area_min":      {"type": ["number","null"]},
                "area_max":      {"type": ["number","null"]},
                "is_completed":  {"type": ["boolean","null"]},
                "sort_by":       {"type": "string",
                                  "enum": ["popular","latest","lowest_price",
                                           "highest_price","verified"]},
                "reply":         {"type": "string",
                                  "description": "Friendly assistant reply in the same language as the user's message, summarizing what was searched."},
                "language":      {"type": "string",
                                  "description": "ISO 639-1 language code of the user's message. e.g. 'ko' for Korean, 'en' for English, 'zh' for Chinese, 'ar' for Arabic, 'ru' for Russian."},
            },
            "required": ["purpose", "categories", "sort_by", "reply", "language"],
        },
    }
]


async def parse_query(message: str, history: list[dict]) -> dict:
    """
    자연어 메시지 → {filters: dict, reply: str}
    """
    messages = []
    for h in history[-10:]:   # 최근 10턴만 전달
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    def _call():
        return _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

    response = await asyncio.to_thread(_call)

    # tool_use 블록 추출
    for block in response.content:
        if block.type == "tool_use" and block.name == "search_properties":
            inp = block.input
            reply = inp.pop("reply", "검색 조건을 적용해 매물을 찾고 있어요.")
            language = inp.pop("language", "ko")
            return {"filters": inp, "reply": reply, "language": language}

    # fallback: tool 미호출 시 텍스트 반환
    text = " ".join(b.text for b in response.content if hasattr(b, "text"))
    return {"filters": None, "reply": text or "조건을 다시 입력해주세요."}

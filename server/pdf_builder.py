"""
PDF 포트폴리오 빌더 — 매물당 1페이지 풀레이아웃
이미지 5장 + 스펙 + 지도 + 가격 차트 + 시장 분석
"""
import io
import os
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, HRFlowable, Image, PageBreak,
    Paragraph, Spacer, Table, TableStyle,
)
import httpx
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 ─────────────────────────────────────────────────────
FR = "KorR"
FB = "KorB"

def _reg_fonts():
    global FR, FB
    if FR in pdfmetrics.getRegisteredFontNames():
        return
    for p in ["/System/Library/Fonts/Supplemental/AppleGothic.ttf",
              "/Library/Fonts/Arial Unicode.ttf"]:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont(FR, p))
                pdfmetrics.registerFont(TTFont(FB, p))
                return
            except Exception:
                continue
    FR, FB = "Helvetica", "Helvetica-Bold"

_reg_fonts()

# ── 색상 ─────────────────────────────────────────────────────
CN = colors.HexColor("#0B2545")   # navy
CG = colors.HexColor("#E8A838")   # gold
CL = colors.HexColor("#F4F7FB")   # light bg
CB = colors.HexColor("#C8D6E8")   # border
CT = colors.HexColor("#1A2A3A")   # text
CM = colors.HexColor("#6B7C93")   # muted
CW = colors.white
CLINK = colors.HexColor("#1A73E8")

W, H   = A4
MARGIN = 15 * mm
CW_    = W - 2 * MARGIN


def _s(name, **kw):
    base = dict(fontName=FR, fontSize=9, textColor=CT, leading=13)
    base.update(kw)
    return ParagraphStyle(name, **base)

S = {
    "cover_t": _s("ct", fontName=FB, fontSize=26, textColor=CW, leading=32),
    "cover_s": _s("cs", fontSize=12, textColor=CG, leading=16),
    "cover_m": _s("cm", fontSize=9,  textColor=CW, leading=14),
    "sec":     _s("sc", fontName=FB, fontSize=12, textColor=CN, spaceBefore=3, spaceAfter=2),
    "h_num":   _s("hn", fontName=FB, fontSize=20, textColor=CG, leading=24),
    "h_title": _s("ht", fontName=FB, fontSize=14, textColor=CN, leading=18),
    "h_loc":   _s("hl", fontSize=9,  textColor=CM, leading=13),
    "price":   _s("pr", fontName=FB, fontSize=20, textColor=CG, leading=24),
    "psub":    _s("ps", fontSize=8,  textColor=CM, leading=11),
    "lbl":     _s("lb", fontName=FB, fontSize=7.5,textColor=CM, leading=11),
    "val":     _s("vl", fontSize=8.5,textColor=CT, leading=12),
    "desc":    _s("dc", fontSize=8,  textColor=CT, leading=12),
    "am":      _s("am", fontSize=7.5,textColor=CM, leading=11),
    "url":     _s("ur", fontSize=7.5,textColor=CLINK, leading=11),
    "th":      _s("th", fontName=FB, fontSize=8,  textColor=CW, leading=11, alignment=1),
    "td":      _s("td", fontSize=7.5,textColor=CT, leading=11, alignment=1),
    "td_l":    _s("tl", fontSize=7.5,textColor=CT, leading=11),
    "fk":      _s("fk", fontName=FB, fontSize=8.5,textColor=CN, leading=13),
    "fv":      _s("fv", fontSize=8.5,textColor=CT, leading=13),
    "ctx":     _s("cx", fontSize=8,  textColor=CT, leading=12),
}


# ── 이미지 로더 ───────────────────────────────────────────────
def _load_img(url: str, max_w: float, max_h: float) -> Optional[Image]:
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=8, follow_redirects=True)
        if resp.status_code != 200:
            return None
        img = Image(io.BytesIO(resp.content))
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None
        ratio = min(max_w / iw, max_h / ih)
        img.drawWidth  = iw * ratio
        img.drawHeight = ih * ratio
        return img
    except Exception:
        return None


def _placeholder(w, h, text="No Image"):
    tbl = Table([[Paragraph(text, _s("ph", fontSize=8, textColor=CM, alignment=1))]],
                colWidths=[w], rowHeights=[h])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), CL),
        ("ALIGN",      (0,0),(-1,-1), "CENTER"),
        ("VALIGN",     (0,0),(-1,-1), "MIDDLE"),
        ("BOX",        (0,0),(-1,-1), 0.5, CB),
    ]))
    return tbl


# ── 가격 차트 ─────────────────────────────────────────────────
def _price_chart(price_history: list, prop_psf: Optional[float],
                 w_pts: float, h_pts: float, lang: str = "ko") -> Optional[Image]:
    if not price_history:
        return None
    DPI = 150
    fig, ax = plt.subplots(figsize=(w_pts/72, h_pts/72), dpi=DPI)
    fig.patch.set_facecolor("#F4F7FB")
    ax.set_facecolor("#F4F7FB")

    periods = [d["period"] for d in price_history]
    values  = [d["value"]  for d in price_history]
    n = len(periods)
    bar_colors = [f"#{int(11 + (232-11)*i/(max(n-1,1))):02X}"
                  f"{int(37 + (168-37)*i/(max(n-1,1))):02X}"
                  f"{int(69 + (56-69)*i/(max(n-1,1))):02X}"
                  for i in range(n)]

    ax.bar(range(n), values, color=bar_colors, width=0.6, zorder=3)
    ax.set_xticks(range(n))
    ax.set_xticklabels(
        [p.replace("-", "\n") for p in periods],
        fontsize=5.5, rotation=0
    )
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.tick_params(labelsize=6)
    ax.set_ylabel("AED / ft²", fontsize=6, color="#6B7C93")
    T_chart = _t(lang)
    ax.set_title(T_chart["price_chart_title"], fontsize=7,
                 color="#0B2545", pad=4)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.spines[:].set_visible(False)

    if prop_psf:
        ax.axhline(prop_psf, color="#E8A838", linewidth=1.2,
                   linestyle="--", zorder=4, label=f"{T_chart['this_prop']} {prop_psf:,.0f}")
        ax.legend(fontsize=5.5, loc="upper left", framealpha=0.7)

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    img = Image(buf)
    ratio = min(w_pts / img.imageWidth, h_pts / img.imageHeight)
    img.drawWidth  = img.imageWidth  * ratio
    img.drawHeight = img.imageHeight * ratio
    return img


# ── 개별 매물 페이지 ──────────────────────────────────────────
def _property_page(idx: int, p: dict, lang: str = "ko") -> list:
    T = _t(lang)
    elems = []
    market   = p.get("market", {}) or {}
    photos   = p.get("photos", []) or []
    map_bytes= p.get("map_bytes")
    location = p.get("location", "")
    title    = p.get("title") or location
    price    = p.get("price", 0)
    area_sqft= p.get("area_sqft")
    bedrooms = p.get("bedrooms")
    category = p.get("category", "")

    est_val  = market.get("estimated_value")
    yield_pct= market.get("rental_yield_pct")
    ph_data  = market.get("price_history", [])
    ctx_text = market.get("market_context", "")

    prop_psf = round(price / area_sqft) if price and area_sqft else None

    # ① 헤더
    hdr = Table([[
        Paragraph(f"#{idx}", S["h_num"]),
        [Paragraph(title, S["h_title"]),
         Paragraph(location, S["h_loc"])],
        Paragraph(_fmt_price(price, p.get("currency","AED")), S["price"]),
    ]], colWidths=[CW_*0.08, CW_*0.62, CW_*0.30])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ALIGN",         (2,0),(2,0),   "RIGHT"),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ]))
    elems.append(hdr)
    elems.append(HRFlowable(width="100%", thickness=1.5, color=CG, spaceAfter=4))

    # ② 이미지 스트립 (있는 개수만큼, 없으면 배너로 대체)
    IMG_H = 50 * mm
    n_slots = max(len(photos), 1) if photos else 0
    n_slots = min(n_slots, 5)
    loaded = [_load_img(u, CW_/max(n_slots,1) - 2, IMG_H - 2) for u in photos[:n_slots]]
    loaded = [x for x in loaded if x]

    if loaded:
        # 이미지가 있을 때: 있는 개수만큼 칸 구성
        img_w = CW_ / len(loaded)
        cells = loaded
        img_strip = Table([cells], colWidths=[img_w]*len(loaded), rowHeights=[IMG_H])
        img_strip.setStyle(TableStyle([
            ("ALIGN",        (0,0),(-1,-1), "CENTER"),
            ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0),(-1,-1), 1),
            ("BOTTOMPADDING",(0,0),(-1,-1), 1),
            ("LEFTPADDING",  (0,0),(-1,-1), 1),
            ("RIGHTPADDING", (0,0),(-1,-1), 1),
            ("BOX",          (0,0),(-1,-1), 0.3, CB),
        ]))
        elems.append(img_strip)
    else:
        # 이미지 없을 때: 정보 배너
        prop_url = p.get("url", "")
        beds_str = ("Studio" if bedrooms == 0 else f"{bedrooms}BR") if bedrooms is not None else ""
        area_str = f"  |  {area_sqft:,.0f} ft²" if area_sqft else ""
        banner_lines = [
            Paragraph(
                f"{category}{('  |  ' + beds_str) if beds_str else ''}{area_str}  |  {location}",
                _s("bi", fontSize=10, textColor=CN, fontName=FB, leading=14, alignment=1)
            ),
            Spacer(1, 3*mm),
            Paragraph(
                T["view_photos"],
                _s("bm", fontSize=8, textColor=CM, leading=12, alignment=1)
            ),
        ]
        if prop_url:
            from reportlab.platypus import Paragraph as P_
            banner_lines.append(
                P_(f'<link href="{prop_url}"><u>{prop_url}</u></link>',
                   _s("bu", fontSize=7, textColor=CLINK, leading=11, alignment=1))
            )
        banner_tbl = Table([[banner_lines]], colWidths=[CW_], rowHeights=[IMG_H])
        banner_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), CL),
            ("VALIGN",     (0,0),(-1,-1), "MIDDLE"),
            ("BOX",        (0,0),(-1,-1), 0.5, CB),
            ("TOPPADDING", (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ]))
        elems.append(banner_tbl)
    elems.append(Spacer(1, 3*mm))

    # ③ 스펙 테이블 + 지도 (좌우)
    SPEC_W = CW_ * 0.55
    MAP_W  = CW_ * 0.42
    MAP_H  = 52 * mm

    status = T["completed"] if p.get("is_completed") else (T["off_plan"] if p.get("is_completed") is False else "-")
    purpose_str = T["for_sale"] if p.get("purpose") == "for-sale" else T["for_rent"]
    beds_label = ("Studio" if bedrooms == 0 else f"{bedrooms}BR") if bedrooms is not None else "-"
    floor_unit = T["floor_unit"]
    baths_val = p.get("bathrooms")
    baths_str = (f"{baths_val}{floor_unit}" if floor_unit else str(baths_val)) if baths_val else "-"

    def _floor_str():
        fl = p.get("floor")
        if not fl:
            return "-"
        tf = p.get("total_floors")
        if floor_unit:
            return f"{fl}{floor_unit}" + (f"/{tf}{floor_unit}" if tf else "")
        return str(fl) + (f"/{tf}" if tf else "")

    spec_rows = [
        (T["price_k"],    _fmt_price(price, p.get("currency","AED")),
         T["beds_k"],     beds_label),
        (T["est_value"],  _fmt_price(est_val, "AED") if est_val else T["analyzing"],
         T["baths_k"],    baths_str),
        (T["yield_k"],    f"{yield_pct}%" if yield_pct else "-",
         T["area_k"],     f"{area_sqft:,.0f} ft²" if area_sqft else "-"),
        (T["purpose_k"],  purpose_str,
         T["type_k"],     category),
        (T["status_k"],   status,
         T["furnish_k"],  p.get("furnishing") or "-"),
        (T["floor_k"],    _floor_str(),
         T["ref_k"],      p.get("permit_number") or "-"),
    ]
    spec_data = [[Paragraph(k1,S["lbl"]),Paragraph(v1,S["val"]),
                  Paragraph(k2,S["lbl"]),Paragraph(v2,S["val"])]
                 for k1,v1,k2,v2 in spec_rows]
    col_spec = [SPEC_W*r for r in [0.22, 0.28, 0.22, 0.28]]
    spec_tbl = Table(spec_data, colWidths=col_spec)
    spec_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LINEBELOW",     (0,0),(-1,-2), 0.3, CB),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [CW, CL]),
    ]))

    # 지도 이미지
    if map_bytes:
        map_img = Image(io.BytesIO(map_bytes))
        ratio = min((MAP_W-4) / map_img.imageWidth, (MAP_H-4) / map_img.imageHeight)
        map_img.drawWidth  = map_img.imageWidth  * ratio
        map_img.drawHeight = map_img.imageHeight * ratio
        map_cell = map_img
    else:
        map_cell = _placeholder(MAP_W-4, MAP_H-4, T["no_map"])

    map_tbl = Table([[map_cell]], colWidths=[MAP_W], rowHeights=[MAP_H])
    map_tbl.setStyle(TableStyle([
        ("ALIGN",  (0,0),(-1,-1), "CENTER"),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("BOX",    (0,0),(-1,-1), 0.5, CB),
    ]))

    two_col = Table([[spec_tbl, map_tbl]], colWidths=[SPEC_W, MAP_W])
    two_col.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("COLPADDING",    (0,0),(-1,-1), 4),
    ]))
    elems.append(two_col)
    elems.append(Spacer(1, 3*mm))

    # ④ 가격 차트
    CHART_H = 38 * mm
    chart = _price_chart(ph_data, prop_psf, CW_, CHART_H, lang)
    if chart:
        elems.append(chart)
    else:
        elems.append(_placeholder(CW_, CHART_H, T["no_data"]))
    elems.append(Spacer(1, 3*mm))

    # ⑤ 시장 분석 + 시설
    amenities_str = "   ·   ".join((p.get("amenities") or []))
    bottom_rows = []
    if ctx_text:
        bottom_rows.append([Paragraph(T["market_analysis"], S["lbl"]),
                             Paragraph(ctx_text, S["ctx"])])
    if amenities_str:
        bottom_rows.append([Paragraph(T["amenities"], S["lbl"]),
                             Paragraph(amenities_str, S["am"])])
    if p.get("description"):
        desc = p["description"][:400].replace("\n"," ") + ("…" if len(p["description"])>400 else "")
        bottom_rows.append([Paragraph(T["desc"], S["lbl"]),
                             Paragraph(desc, S["desc"])])
    if bottom_rows:
        btm = Table(bottom_rows, colWidths=[CW_*0.13, CW_*0.87])
        btm.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("LINEBELOW",     (0,0),(-1,-2), 0.3, CB),
        ]))
        elems.append(btm)
        elems.append(Spacer(1, 2*mm))

    # ⑥ 링크 푸터 — 검색 URL (항상 유효)
    url = p.get("url", "")
    agent = p.get("agent_name") or ""
    phone = p.get("agent_phone") or ""
    agent_str = f"{agent}  {phone}".strip(" ") if agent else "-"
    link_label = T["similar_search"]
    link_html = f'<link href="{url}" color="#1A73E8"><u>{url}</u></link>' if url else "-"

    footer = Table([[
        Paragraph(link_label, S["lbl"]),
        Paragraph(link_html, S["url"]),
        Paragraph(T["agent"], S["lbl"]),
        Paragraph(agent_str, S["val"]),
    ]], colWidths=[CW_*0.12, CW_*0.48, CW_*0.12, CW_*0.28])
    footer.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CL),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEABOVE",     (0,0),(-1,0),  1.2, CG),
    ]))
    elems.append(footer)
    return elems


# ── 번역 테이블 ───────────────────────────────────────────────
TRANSLATIONS = {
    "ko": {
        "portfolio_title": "부동산 매물 포트폴리오",
        "header_title": "부동산 포트폴리오",
        "total_props": lambda n: f"총 {n}개 매물 수록",
        "all_listings": "전체 매물 목록",
        "search_filters": "검색 조건",
        "purpose_label": "목적", "location_label": "지역",
        "type_label": "유형", "price_label": "가격", "rooms_label": "방",
        "for_sale": "매매", "for_rent": "임대",
        "col_location": "위치", "col_type": "유형", "col_price": "가격",
        "col_beds": "방", "col_area": "면적", "col_status": "상태",
        "completed": "완공", "off_plan": "분양중",
        "price_k": "가격", "est_value": "추정 시세", "yield_k": "임대수익률",
        "purpose_k": "목적", "status_k": "완공여부", "floor_k": "층수",
        "beds_k": "침실", "baths_k": "욕실", "area_k": "면적",
        "type_k": "유형", "furnish_k": "가구", "ref_k": "참조번호",
        "analyzing": "분석중", "no_data": "거래 데이터 없음",
        "no_map": "지도 없음", "no_image": "이미지 없음",
        "market_analysis": "시장 분석", "amenities": "시설", "desc": "설명",
        "similar_search": "유사 매물 검색", "agent": "에이전트",
        "view_photos": "사진은 매물 페이지에서 확인하세요",
        "footer": lambda n: f"총 {n}개 매물  ·  propertyfinder.ae  ·  PropertyFinder API via RapidAPI",
        "date_fmt": "%Y년 %m월 %d일  %H:%M",
        "no_limit": "제한없음", "any_rooms": "상관없음",
        "price_chart_title": "가격 변동 이력 (ft²당 중앙 거래가)",
        "this_prop": "이 매물", "floor_unit": "층",
    },
    "en": {
        "portfolio_title": "Property Portfolio",
        "header_title": "Property Portfolio",
        "total_props": lambda n: f"{n} Properties",
        "all_listings": "All Listings",
        "search_filters": "Search Criteria",
        "purpose_label": "Purpose", "location_label": "Location",
        "type_label": "Type", "price_label": "Price", "rooms_label": "Bedrooms",
        "for_sale": "For Sale", "for_rent": "For Rent",
        "col_location": "Location", "col_type": "Type", "col_price": "Price",
        "col_beds": "Beds", "col_area": "Area", "col_status": "Status",
        "completed": "Ready", "off_plan": "Off-Plan",
        "price_k": "Price", "est_value": "Est. Value", "yield_k": "Rental Yield",
        "purpose_k": "Purpose", "status_k": "Status", "floor_k": "Floor",
        "beds_k": "Bedrooms", "baths_k": "Bathrooms", "area_k": "Area",
        "type_k": "Type", "furnish_k": "Furnishing", "ref_k": "Reference",
        "analyzing": "Analyzing", "no_data": "No Transaction Data",
        "no_map": "Map unavailable", "no_image": "No Image",
        "market_analysis": "Market Analysis", "amenities": "Amenities", "desc": "Description",
        "similar_search": "Search Similar", "agent": "Agent",
        "view_photos": "View photos on the listing page",
        "footer": lambda n: f"{n} properties  ·  propertyfinder.ae  ·  PropertyFinder API via RapidAPI",
        "date_fmt": "%B %d, %Y  %H:%M",
        "no_limit": "No limit", "any_rooms": "Any",
        "price_chart_title": "Price Trend (Median AED/ft²)",
        "this_prop": "This listing", "floor_unit": "",
    },
    "zh": {
        "portfolio_title": "房产投资组合",
        "header_title": "房产投资组合",
        "total_props": lambda n: f"共 {n} 套房产",
        "all_listings": "全部房源",
        "search_filters": "搜索条件",
        "purpose_label": "目的", "location_label": "地区",
        "type_label": "类型", "price_label": "价格", "rooms_label": "卧室",
        "for_sale": "出售", "for_rent": "出租",
        "col_location": "位置", "col_type": "类型", "col_price": "价格",
        "col_beds": "卧室", "col_area": "面积", "col_status": "状态",
        "completed": "现房", "off_plan": "期房",
        "price_k": "价格", "est_value": "估值", "yield_k": "租金回报率",
        "purpose_k": "目的", "status_k": "状态", "floor_k": "楼层",
        "beds_k": "卧室", "baths_k": "浴室", "area_k": "面积",
        "type_k": "类型", "furnish_k": "装修", "ref_k": "参考编号",
        "analyzing": "分析中", "no_data": "暂无交易数据",
        "no_map": "地图不可用", "no_image": "暂无图片",
        "market_analysis": "市场分析", "amenities": "设施", "desc": "描述",
        "similar_search": "搜索类似房源", "agent": "经纪人",
        "view_photos": "请在房源页面查看照片",
        "footer": lambda n: f"共 {n} 套房产  ·  propertyfinder.ae  ·  PropertyFinder API via RapidAPI",
        "date_fmt": "%Y年%m月%d日  %H:%M",
        "no_limit": "不限", "any_rooms": "不限",
        "price_chart_title": "价格趋势 (中位价 AED/ft²)",
        "this_prop": "此房源", "floor_unit": "层",
    },
    "ar": {
        "portfolio_title": "محفظة العقارات",
        "header_title": "محفظة العقارات",
        "total_props": lambda n: f"{n} عقارات",
        "all_listings": "جميع العقارات",
        "search_filters": "معايير البحث",
        "purpose_label": "الغرض", "location_label": "الموقع",
        "type_label": "النوع", "price_label": "السعر", "rooms_label": "غرف النوم",
        "for_sale": "للبيع", "for_rent": "للإيجار",
        "col_location": "الموقع", "col_type": "النوع", "col_price": "السعر",
        "col_beds": "غرف", "col_area": "المساحة", "col_status": "الحالة",
        "completed": "جاهز", "off_plan": "على الخريطة",
        "price_k": "السعر", "est_value": "القيمة المقدرة", "yield_k": "العائد الإيجاري",
        "purpose_k": "الغرض", "status_k": "الحالة", "floor_k": "الطابق",
        "beds_k": "غرف نوم", "baths_k": "حمامات", "area_k": "المساحة",
        "type_k": "النوع", "furnish_k": "الأثاث", "ref_k": "رقم المرجع",
        "analyzing": "جاري التحليل", "no_data": "لا توجد بيانات",
        "no_map": "الخريطة غير متاحة", "no_image": "لا توجد صورة",
        "market_analysis": "تحليل السوق", "amenities": "المرافق", "desc": "الوصف",
        "similar_search": "بحث مماثل", "agent": "الوكيل",
        "view_photos": "عرض الصور في صفحة العقار",
        "footer": lambda n: f"{n} عقارات  ·  propertyfinder.ae",
        "date_fmt": "%Y/%m/%d  %H:%M",
        "no_limit": "غير محدود", "any_rooms": "أي",
        "price_chart_title": "اتجاه الأسعار (AED/ft²)",
        "this_prop": "هذا العقار", "floor_unit": "",
    },
}

def _t(lang: str) -> dict:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])


# ── 헤더/푸터 콜백 ────────────────────────────────────────────
def _make_page_cb(generated_at: str, total: int, lang: str = "ko"):
    T = _t(lang)
    def cb(canvas, doc):
        canvas.saveState()
        pg = doc.page
        if pg > 1:
            canvas.setFillColor(CN)
            canvas.rect(0, H-13*mm, W, 13*mm, fill=1, stroke=0)
            canvas.setFillColor(CG)
            canvas.setFont(FB, 9)
            canvas.drawString(MARGIN, H-8.5*mm, f"ANAROCK  MIDDLE EAST  ·  {T['header_title']}")
            canvas.setFillColor(CW)
            canvas.setFont(FR, 8)
            canvas.drawRightString(W-MARGIN, H-8.5*mm, generated_at)
        canvas.setFillColor(CB)
        canvas.rect(0, 0, W, 8*mm, fill=1, stroke=0)
        canvas.setFillColor(CM)
        canvas.setFont(FR, 7)
        canvas.drawString(MARGIN, 3*mm, T["footer"](total))
        canvas.drawRightString(W-MARGIN, 3*mm, f"Page {pg}")
        canvas.restoreState()
    return cb


# ── 전체 목록 요약표 ──────────────────────────────────────────
def _overview_table(props: list[dict], lang: str = "ko") -> Table:
    T = _t(lang)
    hdr = [Paragraph(t, S["th"]) for t in
           ["#", T["col_location"], T["col_type"], T["col_price"],
            T["col_beds"], T["col_area"], T["col_status"]]]
    data = [hdr]
    for i, p in enumerate(props, 1):
        status = T["completed"] if p.get("is_completed") else (T["off_plan"] if p.get("is_completed") is False else "-")
        beds = p.get("bedrooms")
        beds_lbl = "Studio" if beds==0 else (f"{beds}BR" if beds else "-")
        area = p.get("area_sqft")
        data.append([
            Paragraph(str(i), S["td"]),
            Paragraph(p.get("location",""), S["td_l"]),
            Paragraph(p.get("category",""), S["td"]),
            Paragraph(_fmt_price(p.get("price",0), p.get("currency","AED")), S["td"]),
            Paragraph(beds_lbl, S["td"]),
            Paragraph(f"{area:,.0f} ft²" if area else "-", S["td"]),
            Paragraph(status, S["td"]),
        ])
    col_w = [r*CW_ for r in [0.05,0.27,0.14,0.17,0.09,0.14,0.10]]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  CN),
        ("GRID",          (0,0),(-1,-1), 0.4, CB),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]
    for i in range(1, len(data)):
        cmds.append(("BACKGROUND",(0,i),(-1,i), CL if i%2==0 else CW))
    tbl.setStyle(TableStyle(cmds))
    return tbl


# ── 검색 조건 표 ──────────────────────────────────────────────
def _filter_table(f, lang: str = "ko") -> Table:
    T = _t(lang)
    rows = [
        [T["search_filters"], ""],
        [T["purpose_label"],  T["for_sale"] if f.purpose=="for-sale" else T["for_rent"]],
        [T["location_label"], f.location_name or "-"],
        [T["type_label"],     ", ".join(f.categories)],
        [T["price_label"],    _price_range(f, lang)],
        [T["rooms_label"],    _rooms_label(f, lang)],
    ]
    tbl = Table([[Paragraph(k,S["fk"]),Paragraph(v,S["fv"])] for k,v in rows],
                colWidths=[CW_*0.28, CW_*0.72])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0,0),(-1,0),   CN),
        ("SPAN",           (0,0),(1,0)),
        ("ALIGN",          (0,0),(-1,0),   "CENTER"),
        ("ROWBACKGROUNDS", (0,1),(-1,-1),  [CW, CL]),
        ("BACKGROUND",     (0,1),(0,-1),   CL),
        ("GRID",           (0,0),(-1,-1),  0.5, CB),
        ("TOPPADDING",     (0,0),(-1,-1),  4),
        ("BOTTOMPADDING",  (0,0),(-1,-1),  4),
        ("LEFTPADDING",    (0,0),(-1,-1),  7),
    ]))
    return tbl


# ── 메인 ─────────────────────────────────────────────────────
def build_portfolio_pdf(properties: list[dict], filters, output_path: str, language: str = "ko"):
    T = _t(language)
    generated_at = datetime.now().strftime(T["date_fmt"])

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=17*mm, bottomMargin=13*mm,
        title=f"ANAROCK Middle East — {T['portfolio_title']}",
    )

    story = []

    # 커버
    cover = Table([
        [Paragraph("ANAROCK  MIDDLE EAST", S["cover_t"])],
        [Paragraph(T["portfolio_title"], S["cover_s"])],
        [Spacer(1,5*mm)],
        [Paragraph(generated_at, S["cover_m"])],
        [Paragraph(T["total_props"](len(properties)), S["cover_m"])],
    ], colWidths=[CW_])
    cover.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CN),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 16),
        ("LINEBELOW",     (0,1),(-1,1),  2.5, CG),
    ]))
    story.append(cover)
    story.append(Spacer(1,6*mm))
    story.append(_filter_table(filters, language))
    story.append(Spacer(1,6*mm))

    from reportlab.platypus import HRFlowable
    story.append(Paragraph(T["all_listings"], S["sec"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=CG, spaceAfter=4))
    story.append(_overview_table(properties, language))
    story.append(PageBreak())

    # 매물별 페이지
    for i, prop in enumerate(properties, 1):
        story.extend(_property_page(i, prop, language))
        story.append(PageBreak())

    cb = _make_page_cb(generated_at, len(properties), language)
    doc.build(story, onFirstPage=cb, onLaterPages=cb)


# ── 헬퍼 ─────────────────────────────────────────────────────
def _fmt_price(price, currency="AED"):
    if not price:
        return "-"
    if price >= 1_000_000:
        return f"{price/1_000_000:.2f}M {currency}"
    if price >= 1_000:
        return f"{price/1_000:.0f}K {currency}"
    return f"{price:,} {currency}"

def _price_range(f, lang: str = "ko"):
    T = _t(lang)
    if not f.price_min and not f.price_max:
        return T["no_limit"]
    lo = f"{f.price_min:,}" if f.price_min else "0"
    hi = f"{f.price_max:,}" if f.price_max else "∞"
    return f"{lo} ~ {hi} AED"

def _rooms_label(f, lang: str = "ko"):
    T = _t(lang)
    if not f.rooms:
        return T["any_rooms"]
    return ", ".join("Studio" if r==0 else f"{r}BR" for r in f.rooms)

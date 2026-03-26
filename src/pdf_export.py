"""
PDF 리포트 생성 모듈 — 매물당 1페이지 풀레이아웃 + 이미지 + 클릭 가능한 링크
"""
import io
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, HRFlowable, Image, KeepTogether,
    PageBreak, Paragraph, Spacer, Table, TableStyle,
)

from .models import Property, SearchFilters

# ── 폰트 ─────────────────────────────────────────────────────
FONT_REGULAR = "KorRegular"
FONT_BOLD    = "KorBold"

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]

def _register_fonts():
    global FONT_REGULAR, FONT_BOLD
    if FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(FONT_REGULAR, path))
                pdfmetrics.registerFont(TTFont(FONT_BOLD,    path))
                return
            except Exception:
                continue
    FONT_REGULAR = "Helvetica"
    FONT_BOLD    = "Helvetica-Bold"

_register_fonts()

# ── 색상 팔레트 ───────────────────────────────────────────────
C_NAVY   = colors.HexColor("#0B2545")
C_GOLD   = colors.HexColor("#E8A838")
C_LIGHT  = colors.HexColor("#F4F7FB")
C_BORDER = colors.HexColor("#C8D6E8")
C_TEXT   = colors.HexColor("#1A2A3A")
C_MUTED  = colors.HexColor("#6B7C93")
C_GREEN  = colors.HexColor("#27AE60")
C_ORANGE = colors.HexColor("#E67E22")
C_LINK   = colors.HexColor("#1A73E8")
C_WHITE  = colors.white

W, H     = A4
MARGIN   = 16 * mm
CW       = W - 2 * MARGIN   # 콘텐츠 너비


# ── 스타일 팩토리 ─────────────────────────────────────────────
def _s(name, **kw) -> ParagraphStyle:
    base = dict(fontName=FONT_REGULAR, fontSize=9, textColor=C_TEXT, leading=13)
    base.update(kw)
    return ParagraphStyle(name, **base)

S = {
    "cover_title": _s("ct",  fontName=FONT_BOLD,    fontSize=28, textColor=C_WHITE,  leading=34),
    "cover_sub":   _s("cs",  fontName=FONT_REGULAR, fontSize=13, textColor=C_GOLD,   leading=18),
    "cover_meta":  _s("cm",  fontName=FONT_REGULAR, fontSize=10, textColor=C_WHITE,  leading=15),
    "section":     _s("sec", fontName=FONT_BOLD,    fontSize=13, textColor=C_NAVY,   spaceBefore=4, spaceAfter=2),
    "prop_title":  _s("pt",  fontName=FONT_BOLD,    fontSize=16, textColor=C_NAVY,   leading=20),
    "prop_loc":    _s("pl",  fontName=FONT_REGULAR, fontSize=10, textColor=C_MUTED,  leading=14),
    "price":       _s("pr",  fontName=FONT_BOLD,    fontSize=22, textColor=C_GOLD,   leading=26),
    "price_sub":   _s("prs", fontName=FONT_REGULAR, fontSize=9,  textColor=C_MUTED,  leading=12),
    "badge_green": _s("bg",  fontName=FONT_BOLD,    fontSize=8,  textColor=C_WHITE,  leading=11),
    "badge_org":   _s("bo",  fontName=FONT_BOLD,    fontSize=8,  textColor=C_WHITE,  leading=11),
    "lbl":         _s("lb",  fontName=FONT_BOLD,    fontSize=8,  textColor=C_MUTED,  leading=11),
    "val":         _s("vl",  fontName=FONT_REGULAR, fontSize=9,  textColor=C_TEXT,   leading=13),
    "desc":        _s("dc",  fontName=FONT_REGULAR, fontSize=8.5,textColor=C_TEXT,   leading=13),
    "amenity":     _s("am",  fontName=FONT_REGULAR, fontSize=8,  textColor=C_MUTED,  leading=12),
    "url":         _s("ur",  fontName=FONT_REGULAR, fontSize=8,  textColor=C_LINK,   leading=12),
    "th":          _s("th",  fontName=FONT_BOLD,    fontSize=8,  textColor=C_WHITE,  leading=11, alignment=1),
    "td":          _s("td",  fontName=FONT_REGULAR, fontSize=8,  textColor=C_TEXT,   leading=11, alignment=1),
    "td_l":        _s("tdl", fontName=FONT_REGULAR, fontSize=8,  textColor=C_TEXT,   leading=11),
    "fk":          _s("fk",  fontName=FONT_BOLD,    fontSize=9,  textColor=C_NAVY,   leading=13),
    "fv":          _s("fv",  fontName=FONT_REGULAR, fontSize=9,  textColor=C_TEXT,   leading=13),
}


# ── 이미지 다운로드 ───────────────────────────────────────────
def _fetch_image(url: str, max_w: float, max_h: float) -> Optional[Image]:
    """URL에서 이미지를 다운로드해 reportlab Image로 반환. 실패 시 None."""
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=8, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.content
        img = Image(io.BytesIO(data))
        # 비율 유지하며 축소
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None
        ratio = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth  = iw * ratio
        img.drawHeight = ih * ratio
        return img
    except Exception:
        return None


def _placeholder_box(width: float, height: float, text: str = "이미지 없음") -> Table:
    """이미지 없을 때 회색 박스 placeholder"""
    tbl = Table([[Paragraph(text, _s("ph", fontName=FONT_REGULAR, fontSize=9,
                                     textColor=C_MUTED, alignment=1))]],
                colWidths=[width], rowHeights=[height])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
    ]))
    return tbl


# ── 헤더 / 푸터 ───────────────────────────────────────────────
def _make_on_page(generated_at: str, total: int):
    def on_page(canvas, doc):
        canvas.saveState()
        pg = doc.page

        if pg > 1:
            # 헤더 바
            canvas.setFillColor(C_NAVY)
            canvas.rect(0, H - 13*mm, W, 13*mm, fill=1, stroke=0)
            canvas.setFillColor(C_GOLD)
            canvas.setFont(FONT_BOLD, 9)
            canvas.drawString(MARGIN, H - 8.5*mm, "Bayut  부동산 매물 리포트")
            canvas.setFillColor(C_WHITE)
            canvas.setFont(FONT_REGULAR, 8)
            canvas.drawRightString(W - MARGIN, H - 8.5*mm, generated_at)

        # 푸터
        canvas.setFillColor(C_BORDER)
        canvas.rect(0, 0, W, 8*mm, fill=1, stroke=0)
        canvas.setFillColor(C_MUTED)
        canvas.setFont(FONT_REGULAR, 7)
        canvas.drawString(MARGIN, 3*mm,
            f"총 {total}개 매물  ·  bayut.com  ·  데이터 출처: Bayut API via RapidAPI")
        canvas.drawRightString(W - MARGIN, 3*mm, f"Page {pg}")

        canvas.restoreState()
    return on_page


# ── 검색 조건 요약표 ──────────────────────────────────────────
def _filter_table(f: SearchFilters) -> Table:
    def price_range():
        if not f.price_min and not f.price_max:
            return "제한없음"
        lo = f"{f.price_min:,}" if f.price_min else "0"
        hi = f"{f.price_max:,}" if f.price_max else "∞"
        return f"{lo} ~ {hi} AED"

    def rooms_label():
        if not f.rooms:
            return "상관없음"
        return ", ".join("Studio" if r == 0 else f"{r}BR" for r in f.rooms)

    def area_range():
        if not f.area_min and not f.area_max:
            return "제한없음"
        lo = f"{f.area_min:,.0f}" if f.area_min else "0"
        hi = f"{f.area_max:,.0f}" if f.area_max else "∞"
        return f"{lo} ~ {hi} ft²"

    rows = [
        ["검색 조건", ""],
        ["목적",      "매매" if f.purpose == "for-sale" else "임대"],
        ["지역",      f.location_name or "-"],
        ["유형",      ", ".join(f.categories)],
        ["가격",      price_range()],
        ["방 개수",   rooms_label()],
        ["면적",      area_range()],
        ["완공여부",  "완공" if f.is_completed else ("미완공" if f.is_completed is False else "상관없음")],
    ]
    tbl = Table(
        [[Paragraph(k, S["fk"]), Paragraph(v, S["fv"])] for k, v in rows],
        colWidths=[CW * 0.28, CW * 0.72],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),   C_NAVY),
        ("SPAN",           (0, 0), (1, 0)),
        ("ALIGN",          (0, 0), (-1, 0),   "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),  [C_WHITE, C_LIGHT]),
        ("BACKGROUND",     (0, 1), (0, -1),   C_LIGHT),
        ("GRID",           (0, 0), (-1, -1),  0.5, C_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1),  5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1),  5),
        ("LEFTPADDING",    (0, 0), (-1, -1),  8),
    ]))
    return tbl


# ── 전체 목록 요약표 ──────────────────────────────────────────
def _overview_table(properties: list[Property]) -> Table:
    header = [Paragraph(t, S["th"]) for t in
              ["#", "위치", "유형", "가격", "방", "면적", "상태"]]
    data = [header]
    for i, p in enumerate(properties, 1):
        status = "완공" if p.is_completed else ("분양중" if p.is_completed is False else "-")
        data.append([
            Paragraph(str(i),            S["td"]),
            Paragraph(p.location,        S["td_l"]),
            Paragraph(p.category,        S["td"]),
            Paragraph(p.price_formatted, S["td"]),
            Paragraph(p.bedrooms_label,  S["td"]),
            Paragraph(p.area_formatted,  S["td"]),
            Paragraph(status,            S["td"]),
        ])
    col_w = [r * CW for r in [0.05, 0.28, 0.14, 0.17, 0.09, 0.14, 0.10]]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  C_NAVY),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(data)):
        cmds.append(("BACKGROUND", (0, i), (-1, i), C_LIGHT if i % 2 == 0 else C_WHITE))
    tbl.setStyle(TableStyle(cmds))
    return tbl


# ── 개별 매물 풀페이지 카드 ───────────────────────────────────
def _property_page(idx: int, p: Property) -> list:
    elems = []

    # ① 번호 + 제목 + 위치
    title_tbl = Table([[
        Paragraph(f"#{idx}", _s("num", fontName=FONT_BOLD, fontSize=18,
                                textColor=C_GOLD, leading=22)),
        [Paragraph(p.title or p.location, S["prop_title"]),
         Paragraph(p.location, S["prop_loc"])],
    ]], colWidths=[CW * 0.10, CW * 0.90])
    title_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elems.append(title_tbl)
    elems.append(HRFlowable(width="100%", thickness=1.5, color=C_GOLD, spaceAfter=5))

    # ② 이미지 + 가격/핵심 정보 (좌우 분할)
    IMG_W  = CW * 0.54
    IMG_H  = 62 * mm
    INFO_W = CW * 0.42

    # 이미지
    img_elem = None
    for photo_url in p.photos:
        img_elem = _fetch_image(photo_url, IMG_W, IMG_H)
        if img_elem:
            break
    if img_elem is None:
        img_elem = _placeholder_box(IMG_W, IMG_H)

    # 가격 + 뱃지 + 핵심 스펙
    status_text  = "완공"   if p.is_completed       else ("분양중" if p.is_completed is False else "-")
    status_style = S["badge_green"] if p.is_completed else S["badge_org"]
    purpose_kor  = "매매"   if p.purpose == "for-sale" else "임대"
    furnishing   = p.furnishing or "-"

    price_per_sqft = ""
    if p.price and p.area_sqft:
        price_per_sqft = f"(ft² 당 {p.price / p.area_sqft:,.0f} AED)"

    specs = [
        [Paragraph("가격",    S["lbl"]), Paragraph(p.price_formatted, S["price"])],
        [Paragraph("",        S["lbl"]), Paragraph(price_per_sqft,    S["price_sub"])],
        [Paragraph("목적",    S["lbl"]), Paragraph(purpose_kor,       S["val"])],
        [Paragraph("완공",    S["lbl"]), Paragraph(status_text,       S["val"])],
        [Paragraph("침실",    S["lbl"]), Paragraph(p.bedrooms_label,  S["val"])],
        [Paragraph("욕실",    S["lbl"]), Paragraph(f"{p.bathrooms or '-'}개", S["val"])],
        [Paragraph("면적",    S["lbl"]), Paragraph(p.area_formatted,  S["val"])],
        [Paragraph("유형",    S["lbl"]), Paragraph(p.category,        S["val"])],
        [Paragraph("가구",    S["lbl"]), Paragraph(furnishing,        S["val"])],
    ]
    if p.floor:
        specs.append([Paragraph("층수", S["lbl"]),
                      Paragraph(f"{p.floor}층" + (f" / 전체 {p.total_floors}층" if p.total_floors else ""),
                                S["val"])])

    spec_tbl = Table(specs, colWidths=[INFO_W * 0.36, INFO_W * 0.64])
    spec_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_BORDER),
    ]))

    two_col = Table([[img_elem, spec_tbl]],
                    colWidths=[IMG_W, INFO_W],
                    hAlign="LEFT")
    two_col.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (1, 0), (1, 0),   0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("COLPADDING",   (0, 0), (-1, -1), 4),
    ]))
    elems.append(two_col)
    elems.append(Spacer(1, 4*mm))

    # ③ 상세 정보 4열 그리드
    detail_items = [
        ("참조번호",  p.permit_number or "-"),
        ("에이전트",  p.agent_name    or "-"),
        ("에이전시",  p.agency_name   or "-"),
        ("연락처",    p.agent_phone   or "-"),
    ]
    detail_rows = []
    for i in range(0, len(detail_items), 2):
        row = []
        for k, v in detail_items[i:i+2]:
            row += [Paragraph(k, S["lbl"]), Paragraph(v, S["val"])]
        if len(row) < 4:
            row += [Paragraph("", S["lbl"]), Paragraph("", S["val"])]
        detail_rows.append(row)

    col_ratio = [0.16, 0.34, 0.16, 0.34]
    d_tbl = Table(detail_rows, colWidths=[CW * r for r in col_ratio])
    d_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    elems.append(d_tbl)
    elems.append(Spacer(1, 4*mm))

    # ④ 설명문
    if p.description:
        desc_text = p.description.replace("\n", " ").strip()
        if len(desc_text) > 600:
            desc_text = desc_text[:597] + "..."
        desc_tbl = Table(
            [[Paragraph("매물 설명", S["lbl"]),
              Paragraph(desc_text, S["desc"])]],
            colWidths=[CW * 0.14, CW * 0.86],
        )
        desc_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_BORDER),
        ]))
        elems.append(desc_tbl)
        elems.append(Spacer(1, 3*mm))

    # ⑤ 시설 태그
    if p.amenities:
        amenity_str = "   ·   ".join(p.amenities)
        am_tbl = Table(
            [[Paragraph("시설", S["lbl"]),
              Paragraph(amenity_str, S["amenity"])]],
            colWidths=[CW * 0.14, CW * 0.86],
        )
        am_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        elems.append(am_tbl)
        elems.append(Spacer(1, 3*mm))

    # ⑥ 링크 (클릭 가능)
    link_html = f'<link href="{p.url}" color="#1A73E8"><u>{p.url}</u></link>'
    link_tbl = Table(
        [[Paragraph("매물 링크", S["lbl"]),
          Paragraph(link_html, S["url"])]],
        colWidths=[CW * 0.14, CW * 0.86],
    )
    link_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("LINEABOVE",     (0, 0), (-1, 0),  1, C_GOLD),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elems.append(link_tbl)

    return elems


# ── 메인 함수 ─────────────────────────────────────────────────
def generate_pdf(
    properties: list[Property],
    filters: SearchFilters,
    output_path: Optional[str] = None,
) -> str:
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(Path.home() / "Downloads" / f"bayut_report_{ts}.pdf")

    generated_at = datetime.now().strftime("%Y년 %m월 %d일  %H:%M")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=14 * mm,
        title="Bayut 부동산 매물 리포트",
        author="Bayut Filter App",
    )

    story = []

    # ── 커버 섹션 ─────────────────────────────────────────────
    cover_rows = [
        [Paragraph("Bayut", S["cover_title"])],
        [Paragraph("부동산 매물 리포트", S["cover_sub"])],
        [Spacer(1, 8*mm)],
        [Paragraph(generated_at, S["cover_meta"])],
        [Paragraph(f"총 {len(properties)}개 매물 수록", S["cover_meta"])],
    ]
    cover_tbl = Table(cover_rows, colWidths=[CW])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 18),
        ("LINEBELOW",     (0, 1), (-1, 1),  2.5, C_GOLD),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 7*mm))

    # 검색 조건
    story.append(_filter_table(filters))
    story.append(Spacer(1, 7*mm))

    # 전체 목록 표
    story.append(Paragraph("전체 매물 목록", S["section"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_GOLD, spaceAfter=4))
    story.append(_overview_table(properties))
    story.append(PageBreak())

    # ── 매물별 풀페이지 ───────────────────────────────────────
    for i, prop in enumerate(properties, 1):
        story.extend(_property_page(i, prop))
        story.append(PageBreak())

    doc.build(
        story,
        onFirstPage=_make_on_page(generated_at, len(properties)),
        onLaterPages=_make_on_page(generated_at, len(properties)),
    )
    return output_path

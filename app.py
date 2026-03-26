"""
Bayut 부동산 필터 - Streamlit 웹 UI
실행: streamlit run app.py
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Bayut 매물 필터", page_icon="🏠", layout="wide")
st.title("🏠 Bayut 부동산 매물 필터")
st.caption("UAE(두바이 등) 실시간 매물 검색")

# API Key 체크
api_key = os.getenv("RAPIDAPI_KEY", "")
if not api_key or api_key == "your_rapidapi_key_here":
    st.error("⚠️ `.env` 파일에 `RAPIDAPI_KEY`를 설정해주세요.")
    st.code("RAPIDAPI_KEY=your_key_here", language="bash")
    st.markdown("키 발급: [RapidAPI → Bayut](https://rapidapi.com)")
    st.stop()

from src.models import SearchFilters
from src import api as bayut_api

# ── 사이드바 필터 ──────────────────────────────────────────────
with st.sidebar:
    st.header("필터 설정")

    purpose = st.radio("목적", ["매매", "임대"], horizontal=True)

    category = st.selectbox(
        "부동산 유형",
        ["apartments", "villas", "townhouses", "penthouses", "studios", "offices", "retail"],
    )

    location_query = st.text_input("위치 검색", placeholder="예: Dubai Marina")
    location_id = None
    location_name = ""

    if location_query:
        try:
            loc_results = bayut_api.search_locations(location_query)
            if loc_results:
                options = {
                    (r.get("name_en") or r.get("name") or str(r["id"])): r["id"]
                    for r in loc_results[:8]
                }
                selected_name = st.selectbox("위치 선택", list(options.keys()))
                location_id = options[selected_name]
                location_name = selected_name
            else:
                st.warning("위치 결과 없음")
        except Exception as e:
            st.error(f"위치 검색 오류: {e}")

    st.subheader("가격 (AED)")
    col1, col2 = st.columns(2)
    price_min = col1.number_input("최저", min_value=0, value=0, step=50000)
    price_max = col2.number_input("최고", min_value=0, value=0, step=50000)

    rooms_options = st.multiselect(
        "방 개수",
        options=[0, 1, 2, 3, 4, 5],
        format_func=lambda x: "Studio" if x == 0 else f"{x}BR",
    )

    st.subheader("면적 (sqft)")
    col3, col4 = st.columns(2)
    area_min = col3.number_input("최소", min_value=0, value=0, step=100)
    area_max = col4.number_input("최대", min_value=0, value=0, step=100)

    completed = st.selectbox("완공 여부", ["상관없음", "완공", "미완공"])

    sort_map = {
        "인기순": "popular",
        "최신순": "latest",
        "가격 낮은순": "lowest_price",
        "가격 높은순": "highest_price",
    }
    sort_label = st.selectbox("정렬", list(sort_map.keys()))

    search_btn = st.button("🔍 검색", use_container_width=True, type="primary")

# ── 검색 실행 ─────────────────────────────────────────────────
if search_btn:
    filters = SearchFilters(
        purpose="for-sale" if purpose == "매매" else "for-rent",
        categories=[category],
        locations_ids=[location_id] if location_id else [],
        location_name=location_name,
        price_min=price_min or None,
        price_max=price_max or None,
        rooms=rooms_options or None,
        area_min=float(area_min) or None,
        area_max=float(area_max) or None,
        is_completed=True if completed == "완공" else (False if completed == "미완공" else None),
        sort_by=sort_map[sort_label],
    )

    with st.spinner("매물 검색 중..."):
        try:
            properties, total = bayut_api.search_properties(filters, page=0)
        except Exception as e:
            st.error(f"API 오류: {e}")
            st.stop()

    st.success(f"총 **{total:,}건** 중 **{len(properties)}건** 표시")

    if not properties:
        st.info("조건에 맞는 매물이 없습니다. 필터를 조정해보세요.")
    else:
        # ── PDF 내보내기 ────────────────────────────────────────
        st.subheader("PDF 리포트 저장")
        all_nums = list(range(1, len(properties) + 1))
        selected_nums = st.multiselect(
            "PDF에 포함할 매물 선택 (비워두면 전체 포함)",
            options=all_nums,
            format_func=lambda i: f"{i}. {properties[i-1].location} — {properties[i-1].price_formatted}",
        )

        if st.button("📄 PDF 생성", type="primary"):
            selected = [properties[i - 1] for i in selected_nums] if selected_nums else properties
            with st.spinner(f"{len(selected)}개 매물로 PDF 생성 중..."):
                try:
                    import tempfile
                    from src.pdf_export import generate_pdf
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp_path = tmp.name
                    generate_pdf(selected, filters, output_path=tmp_path)
                    with open(tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                    from datetime import datetime
                    filename = f"bayut_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    st.download_button(
                        label="⬇️ PDF 다운로드",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                    )
                    st.success("PDF 생성 완료! 위 버튼으로 다운로드하세요.")
                except Exception as e:
                    st.error(f"PDF 생성 오류: {e}")

        st.divider()

        # ── 매물 목록 ───────────────────────────────────────────
        for i, p in enumerate(properties, 1):
            with st.expander(
                f"**{i}. {p.location}** — {p.price_formatted} | {p.bedrooms_label} | {p.area_formatted}",
                expanded=(i == 1),
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("가격", p.price_formatted)
                c2.metric("방/욕실", f"{p.bedrooms_label} / {p.bathrooms or '-'}욕실")
                c3.metric("면적", p.area_formatted)

                st.write(f"**유형:** {p.category}  |  **상태:** {'완공' if p.is_completed else '미완공' if p.is_completed is False else '미상'}")
                if p.agent_name:
                    st.write(f"**에이전트:** {p.agent_name}" + (f" ({p.agency_name})" if p.agency_name else ""))
                if p.amenities:
                    st.write(f"**시설:** {', '.join(p.amenities[:8])}")
                st.markdown(f"[매물 바로가기]({p.url})")

else:
    st.info("왼쪽 사이드바에서 필터를 설정하고 검색 버튼을 눌러주세요.")

# -*- coding: utf-8 -*-
"""
제주 카페 지도 · 분석 앱
- 데이터: jeju_cafes.parquet (원본 제주상권.xlsx에서 카페만 추출·경량화)
- 실행: streamlit run app.py
"""
import math
from io import BytesIO

import pandas as pd
import streamlit as st
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import plotly.express as px

# ──────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="제주 카페 탐방",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = "jeju_cafes.parquet"
JEJU_CENTER = (33.42, 126.55)

# 펫 프렌들리 "추정"용 키워드 (데이터에 실제 컬럼이 없어 상호명 기반 추정)
PET_KEYWORDS = ["펫", "반려", "강아지", "애견", "멍", "댕", "도그", "dog", "냥", "고양이", "캣"]

# 커피 하우스 무드 팔레트
C_CREAM = "#F5EFE6"
C_LATTE = "#E8DFCA"
C_MOCHA = "#6F4E37"
C_ESPRESSO = "#3B2C24"
C_CARAMEL = "#B07B4F"
C_SAGE = "#8A9A5B"


# ──────────────────────────────────────────────────────────────
# 디자인 (따뜻한 커피하우스 무드 / Behance '카페 탐방' 느낌)
# ──────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: linear-gradient(180deg, {C_CREAM} 0%, #EFE7D9 100%);
        }}
        /* 헤더 히어로 */
        .hero {{
            background: linear-gradient(135deg, {C_ESPRESSO} 0%, {C_MOCHA} 100%);
            border-radius: 22px;
            padding: 38px 44px;
            color: {C_CREAM};
            margin-bottom: 22px;
            box-shadow: 0 12px 34px rgba(59,44,36,0.28);
        }}
        .hero h1 {{
            font-size: 2.5rem; font-weight: 800; margin: 0 0 6px 0;
            letter-spacing: -0.5px;
        }}
        .hero p {{ font-size: 1.02rem; opacity: 0.85; margin: 0; }}
        .hero .pill {{
            display:inline-block; background: rgba(245,239,230,0.16);
            padding: 4px 14px; border-radius: 999px; font-size: 0.82rem;
            margin-top: 14px; letter-spacing: 1px;
        }}
        /* KPI 카드 */
        .kpi {{
            background: #FFFDF8; border: 1px solid {C_LATTE};
            border-radius: 16px; padding: 20px 22px; text-align: center;
            box-shadow: 0 4px 16px rgba(111,78,55,0.08);
            height: 100%;
        }}
        .kpi .num {{ font-size: 2.1rem; font-weight: 800; color: {C_MOCHA}; line-height: 1; }}
        .kpi .lbl {{ font-size: 0.86rem; color: #8B7B6B; margin-top: 8px; }}
        /* 섹션 제목 */
        .sec-title {{
            font-size: 1.35rem; font-weight: 800; color: {C_ESPRESSO};
            margin: 6px 0 12px 0; border-left: 6px solid {C_CARAMEL};
            padding-left: 12px;
        }}
        /* 탭 */
        .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
        .stTabs [data-baseweb="tab"] {{
            background: #FFFDF8; border-radius: 12px 12px 0 0;
            padding: 10px 20px; font-weight: 700; color: {C_MOCHA};
        }}
        .stTabs [aria-selected="true"] {{
            background: {C_MOCHA} !important; color: {C_CREAM} !important;
        }}
        /* 사이드바 */
        section[data-testid="stSidebar"] {{ background: #FBF7EF; }}
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2 {{ color: {C_ESPRESSO}; }}
        /* 다운로드/버튼 */
        .stDownloadButton button, .stButton button {{
            background: {C_MOCHA}; color: {C_CREAM}; border: none;
            border-radius: 10px; font-weight: 700;
        }}
        .stDownloadButton button:hover, .stButton button:hover {{
            background: {C_CARAMEL}; color: #fff;
        }}
        .note {{
            background: #FFF6E6; border: 1px dashed {C_CARAMEL};
            border-radius: 10px; padding: 10px 14px; font-size: 0.86rem;
            color: #7A5A3A;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# 데이터 로딩 · 정제 (캐싱)
#   원본 제주상권.xlsx에서 카페 행·필요 컬럼만 추출해 parquet로 경량화했으므로
#   여기서는 결측 보정과 펫 프렌들리 추정만 수행한다.
# ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="제주 카페 데이터를 불러오는 중...")
def load_data(path: str) -> pd.DataFrame:
    cafe = pd.read_parquet(path)

    cafe["name"] = cafe["name"].fillna("(상호명 미상)").astype(str)
    cafe["road_addr"] = cafe["road_addr"].fillna(cafe["jibun_addr"]).fillna("")
    cafe["dong"] = cafe["dong"].fillna("기타").astype(str)

    # 펫 프렌들리 추정 (상호명 키워드 기반 — 실제 컬럼 없음)
    low = cafe["name"].str.lower()
    cafe["pet_guess"] = low.apply(
        lambda s: any(k.lower() in s for k in PET_KEYWORDS)
    )

    cafe = cafe.reset_index(drop=True)
    return cafe


def haversine(lat1, lon1, lat2, lon2):
    """두 좌표 간 거리(km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────
# 앱 시작
# ──────────────────────────────────────────────────────────────
inject_css()
df = load_data(DATA_PATH)

st.markdown(
    f"""
    <div class="hero">
        <h1>☕ 제주 카페 탐방</h1>
        <p>제주도 카페 {len(df):,}곳을 지도와 데이터로 살펴보는 탐방 가이드</p>
        <span class="pill">JEJU CAFE MAP · DATA GUIDE</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── 사이드바 필터 ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 탐방 필터")

    cities = ["전체"] + sorted(df["city"].dropna().unique().tolist())
    sel_city = st.selectbox("시 / 군 / 구", cities)

    if sel_city != "전체":
        dong_pool = df[df["city"] == sel_city]
    else:
        dong_pool = df
    dongs = ["전체"] + sorted(dong_pool["dong"].dropna().unique().tolist())
    sel_dong = st.selectbox("행정동", dongs)

    kw = st.text_input("상호명 검색", placeholder="예: 골드문, 오션뷰...")

    pet_only = st.checkbox("🐾 펫 프렌들리 카페만 (추정)")
    if pet_only:
        st.markdown(
            '<div class="note">⚠️ 원본 데이터에 애견동반 정보가 없어 '
            '<b>상호명 키워드로 추정</b>한 결과입니다. 방문 전 확인 필요.</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption("데이터: 소상공인시장진흥공단 상가업소 (제주)")

# ── 필터 적용 ─────────────────────────────────────────────────
f = df.copy()
if sel_city != "전체":
    f = f[f["city"] == sel_city]
if sel_dong != "전체":
    f = f[f["dong"] == sel_dong]
if kw.strip():
    f = f[f["name"].str.contains(kw.strip(), case=False, na=False)]
if pet_only:
    f = f[f["pet_guess"]]

# ── KPI 카드 ──────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
kpis = [
    (k1, f"{len(f):,}", "선택된 카페"),
    (k2, f"{f['dong'].nunique()}", "포함 행정동"),
    (k3, f"{f['city'].nunique()}", "시·군·구"),
    (k4, f"{int(f['pet_guess'].sum()):,}", "펫 프렌들리(추정)"),
]
for col, num, lbl in kpis:
    col.markdown(
        f'<div class="kpi"><div class="num">{num}</div>'
        f'<div class="lbl">{lbl}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

if f.empty:
    st.warning("조건에 맞는 카페가 없습니다. 필터를 조정해 보세요.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# 탭
# ──────────────────────────────────────────────────────────────
tab_map, tab_near, tab_dash, tab_list = st.tabs(
    ["🗺️ 카페 지도", "📍 내 주변 카페", "📊 분석 대시보드", "📋 목록 · 다운로드"]
)

# ── 탭 1: 지도 ────────────────────────────────────────────────
with tab_map:
    st.markdown('<div class="sec-title">카페 위치 지도</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        view = st.radio("표시 방식", ["마커 클러스터", "히트맵(밀집도)"], index=0)
        st.caption(f"현재 {len(f):,}개 카페 표시 중")

    # 지도 중심: 필터 결과 평균
    center = (f["lat"].mean(), f["lon"].mean())
    m = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")

    if view == "마커 클러스터":
        cluster = MarkerCluster(name="카페").add_to(m)
        # 성능: 마커는 최대 1500개 샘플, 히트맵은 전량
        show = f if len(f) <= 1500 else f.sample(1500, random_state=1)
        for _, r in show.iterrows():
            popup = folium.Popup(
                f"<b>{r['name']}</b><br>{r['dong']}<br>"
                f"<span style='color:#6F4E37'>{r['road_addr']}</span>",
                max_width=260,
            )
            folium.Marker(
                [r["lat"], r["lon"]],
                popup=popup,
                tooltip=r["name"],
                icon=folium.Icon(color="cadetblue", icon="coffee", prefix="fa"),
            ).add_to(cluster)
        if len(f) > 1500:
            st.markdown(
                '<div class="note">🔎 카페가 많아 지도에는 1,500개를 '
                "샘플로 표시합니다. 필터를 좁히면 전부 보여요.</div>",
                unsafe_allow_html=True,
            )
    else:
        HeatMap(
            f[["lat", "lon"]].values.tolist(),
            radius=13, blur=18, min_opacity=0.35,
        ).add_to(m)

    st_folium(m, use_container_width=True, height=560, returned_objects=[])

# ── 탭 2: 내 주변 카페 ────────────────────────────────────────
with tab_near:
    st.markdown('<div class="sec-title">내 주변 카페 찾기</div>', unsafe_allow_html=True)
    st.caption("기준 위치(위도·경도)를 입력하면 가까운 카페를 거리순으로 찾아드려요.")

    presets = {
        "직접 입력": None,
        "제주공항": (33.5070, 126.4930),
        "제주시청": (33.4996, 126.5312),
        "성산일출봉": (33.4580, 126.9425),
        "서귀포시청": (33.2542, 126.5600),
        "협재해수욕장": (33.3940, 126.2396),
    }
    p1, p2, p3 = st.columns([1.2, 1, 1])
    with p1:
        preset = st.selectbox("기준 위치", list(presets))
    default = presets[preset] or JEJU_CENTER
    with p2:
        my_lat = st.number_input("위도", value=float(default[0]), format="%.5f")
    with p3:
        my_lon = st.number_input("경도", value=float(default[1]), format="%.5f")

    topn = st.slider("추천 개수", 3, 20, 8)

    near = f.copy()
    near["dist_km"] = near.apply(
        lambda r: haversine(my_lat, my_lon, r["lat"], r["lon"]), axis=1
    )
    near = near.nsmallest(topn, "dist_km")

    mc1, mc2 = st.columns([3, 2])
    with mc1:
        nm = folium.Map(location=(my_lat, my_lon), zoom_start=13,
                        tiles="CartoDB positron")
        folium.Marker(
            [my_lat, my_lon], tooltip="내 위치",
            icon=folium.Icon(color="red", icon="user", prefix="fa"),
        ).add_to(nm)
        for rank, (_, r) in enumerate(near.iterrows(), 1):
            folium.Marker(
                [r["lat"], r["lon"]],
                tooltip=f"{rank}. {r['name']} ({r['dist_km']:.2f}km)",
                popup=folium.Popup(
                    f"<b>{rank}. {r['name']}</b><br>{r['road_addr']}"
                    f"<br>거리 {r['dist_km']:.2f} km", max_width=260),
                icon=folium.Icon(color="cadetblue", icon="coffee", prefix="fa"),
            ).add_to(nm)
        st_folium(nm, use_container_width=True, height=460, returned_objects=[])
    with mc2:
        disp = near[["name", "dong", "dist_km", "road_addr"]].copy()
        disp.insert(0, "순위", range(1, len(disp) + 1))
        disp["dist_km"] = disp["dist_km"].round(2)
        disp = disp.rename(columns={
            "name": "카페", "dong": "행정동",
            "dist_km": "거리(km)", "road_addr": "주소"})
        st.dataframe(disp, hide_index=True, use_container_width=True, height=460)

# ── 탭 3: 분석 대시보드 ───────────────────────────────────────
with tab_dash:
    st.markdown('<div class="sec-title">지역별 카페 분석</div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    with d1:
        by_city = f["city"].value_counts().reset_index()
        by_city.columns = ["시군구", "카페수"]
        fig1 = px.pie(
            by_city, names="시군구", values="카페수", hole=0.55,
            color_discrete_sequence=[C_MOCHA, C_CARAMEL, C_SAGE, C_LATTE],
        )
        fig1.update_layout(
            title="시·군·구별 카페 비중", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color=C_ESPRESSO,
            margin=dict(t=50, b=10, l=10, r=10), height=360,
        )
        st.plotly_chart(fig1, use_container_width=True)

    with d2:
        rank = (f["dong"].value_counts().head(15)
                .sort_values().reset_index())
        rank.columns = ["행정동", "카페수"]
        fig2 = px.bar(
            rank, x="카페수", y="행정동", orientation="h",
            color="카페수", color_continuous_scale=["#E8DFCA", C_MOCHA],
            text="카페수",
        )
        fig2.update_layout(
            title="🏆 카페 밀집 행정동 TOP 15", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color=C_ESPRESSO,
            margin=dict(t=50, b=10, l=10, r=10), height=360,
            coloraxis_showscale=False,
        )
        fig2.update_traces(textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)

    # 밀집 랭킹 표
    st.markdown('<div class="sec-title">동네별 밀집 랭킹</div>', unsafe_allow_html=True)
    full_rank = f["dong"].value_counts().reset_index()
    full_rank.columns = ["행정동", "카페수"]
    full_rank.insert(0, "순위", range(1, len(full_rank) + 1))
    full_rank["비중(%)"] = (full_rank["카페수"] / len(f) * 100).round(1)
    st.dataframe(full_rank, hide_index=True, use_container_width=True, height=340)

# ── 탭 4: 목록 · 다운로드 ─────────────────────────────────────
with tab_list:
    st.markdown('<div class="sec-title">카페 목록</div>', unsafe_allow_html=True)
    show_cols = {
        "name": "상호명", "city": "시군구", "dong": "행정동",
        "road_addr": "도로명주소", "lat": "위도", "lon": "경도",
    }
    table = f[list(show_cols)].rename(columns=show_cols).reset_index(drop=True)
    st.dataframe(table, hide_index=True, use_container_width=True, height=460)

    csv = table.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 현재 목록 CSV 다운로드",
        data=csv,
        file_name="jeju_cafes.csv",
        mime="text/csv",
    )

    xbuf = BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as w:
        table.to_excel(w, index=False, sheet_name="cafes")
    st.download_button(
        "⬇️ 현재 목록 Excel 다운로드",
        data=xbuf.getvalue(),
        file_name="jeju_cafes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown(
    f"<p style='text-align:center;color:#A0937F;margin-top:26px;font-size:0.82rem'>"
    f"☕ 제주 카페 탐방 · 데이터 기반 카페 가이드 · 총 {len(df):,}곳</p>",
    unsafe_allow_html=True,
)

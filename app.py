from datetime import datetime, timedelta, timezone

import geopandas as gpd
import streamlit as st

from modules.load_data import (
    load_data,
    load_building_shadow_timeseries,
)
from modules.map_3d import show_3d_map
from modules.weather_api import latlon_to_grid
from modules.weather_service import build_weather_data
from modules.risk_engine import (
    calculate_weather_score,
    calculate_location_weight,
    calculate_final_score,
    classify_risk,
    generate_ai_summary,
    estimate_surface_temperature,
    estimate_dew_point,
)


# 배포 서버의 시스템 시간대와 관계없이 한국 표준시를 사용한다.
KST = timezone(timedelta(hours=9))


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="AI Smart De-Ice",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# STYLE
# =========================================================

st.markdown(
    """
<style>
:root {
    --bg: #06111f;
    --sidebar: #071827;
    --panel: #0b1d30;
    --panel2: #0e243a;
    --border: rgba(112, 160, 207, 0.20);
    --text: #f5f8fc;
    --muted: #8ea4bf;
    --blue: #29b6f6;
    --green: #10c56f;
    --yellow: #ffc928;
    --orange: #ff922b;
    --red: #ff3547;
}

html, body, [class*="css"] {
    font-family: "Pretendard", "Noto Sans KR", "Segoe UI", sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 75% 10%, rgba(14, 72, 118, 0.15), transparent 30%),
        linear-gradient(180deg, #071321 0%, #06111f 100%);
    color: var(--text);
}

[data-testid="stHeader"] {
    background: rgba(6, 17, 31, 0.82);
    backdrop-filter: blur(10px);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #081a2a 0%, #061423 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.8rem;
}

.block-container {
    max-width: 1580px;
    padding-top: 4.3rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    letter-spacing: -0.03em;
}

.hero-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 1.2rem;
}

.hero-title {
    font-size: 2.25rem;
    font-weight: 900;
    color: var(--text);
    line-height: 1.1;
    margin-bottom: 0.35rem;
}

.hero-subtitle {
    color: #9bb0c8;
    font-size: 0.96rem;
}

.update-box {
    min-width: 190px;
    background: rgba(10, 30, 49, 0.92);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    color: #a9bad0;
    font-size: 0.74rem;
    line-height: 1.6;
}

/* ======================================================
   KPI CARD - 큰 아이콘형
   ====================================================== */

.kpi-card {
    background:
        radial-gradient(circle at 88% 12%, rgba(40, 116, 180, 0.10), transparent 38%),
        linear-gradient(180deg, rgba(15, 36, 58, 0.99), rgba(10, 26, 43, 0.99));
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1rem 1.05rem;
    min-height: 142px;
    box-shadow: 0 14px 34px rgba(0,0,0,0.16);
}

.kpi-top {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}

.kpi-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.9rem;
    line-height: 1;
    flex: 0 0 auto;
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: inset 0 0 16px rgba(255,255,255,0.025);
}

.kpi-label {
    color: #a8bad0;
    font-size: 0.83rem;
    font-weight: 800;
    line-height: 1.3;
}

.kpi-value {
    font-size: 1.78rem;
    line-height: 1.05;
    color: var(--text);
    font-weight: 900;
    letter-spacing: -0.02em;
}

.kpi-sub {
    color: #738daa;
    font-size: 0.73rem;
    margin-top: 0.48rem;
}

.icon-green {
    background: rgba(16, 197, 111, 0.10);
    border-color: rgba(16, 197, 111, 0.22);
}

.icon-red {
    background: rgba(255, 53, 71, 0.10);
    border-color: rgba(255, 53, 71, 0.22);
}

.icon-yellow {
    background: rgba(255, 201, 40, 0.10);
    border-color: rgba(255, 201, 40, 0.22);
}

.icon-blue {
    background: rgba(41, 182, 246, 0.10);
    border-color: rgba(41, 182, 246, 0.22);
}

.icon-purple {
    background: rgba(139, 92, 246, 0.10);
    border-color: rgba(139, 92, 246, 0.22);
}

.v-green { color: var(--green); }
.v-yellow { color: var(--yellow); }
.v-red { color: var(--red); }
.v-blue { color: var(--blue); }

.legend-panel {
    background: rgba(10, 27, 45, 0.94);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.78rem 0.95rem;
    margin: 1.05rem 0 1rem 0;
}

.legend-wrap {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 20px;
    color: #b8c6d6;
    font-size: 0.76rem;
}

.legend-title {
    font-weight: 850;
    color: #eef5fc;
    margin-right: 8px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 7px;
}

.legend-line {
    width: 31px;
    height: 5px;
    border-radius: 99px;
}

.section-title {
    font-size: 1.03rem;
    font-weight: 850;
    color: #edf5fd;
    margin: 1.0rem 0 0.7rem 0;
}

/* ======================================================
   WEATHER CARD - 아이콘 확대
   ====================================================== */

.weather-card {
    background:
        radial-gradient(circle at 88% 12%, rgba(54, 141, 208, 0.08), transparent 36%),
        linear-gradient(180deg, rgba(15, 36, 58, 0.98), rgba(10, 26, 43, 0.98));
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 1rem 1.05rem;
    min-height: 124px;
}

.weather-top {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 0.7rem;
}

.weather-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.65rem;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
}

.weather-label {
    color: #a4b7cc;
    font-size: 0.82rem;
    font-weight: 800;
}

.weather-value {
    font-size: 1.7rem;
    font-weight: 900;
    color: var(--text);
    letter-spacing: -0.02em;
}

.result-card {
    background: linear-gradient(180deg, rgba(15, 36, 58, 0.98), rgba(10, 26, 43, 0.98));
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.05rem 1.15rem;
    min-height: 185px;
}

.result-title {
    color: #edf5fd;
    font-size: 0.95rem;
    font-weight: 850;
    margin-bottom: 0.65rem;
}

.result-main {
    font-size: 1.18rem;
    font-weight: 900;
    color: var(--text);
    margin-bottom: 0.8rem;
}

.result-label {
    color: #8199b4;
    font-size: 0.74rem;
    margin-top: 0.5rem;
}

.result-value {
    color: #edf5fd;
    font-size: 1.2rem;
    font-weight: 850;
}

.footer-note {
    text-align: center;
    color: #60758d;
    font-size: 0.72rem;
    margin-top: 1.3rem;
}

.sidebar-source {
    background: rgba(11, 31, 51, 0.9);
    border: 1px solid rgba(112, 160, 207, 0.18);
    border-radius: 12px;
    padding: 0.85rem 0.9rem;
    color: #8fa5bd;
    font-size: 0.72rem;
    line-height: 1.5;
}

.stButton > button {
    width: 100%;
    min-height: 3.1rem;
    border-radius: 10px;
    font-weight: 850;
    border: 1px solid rgba(62, 154, 255, 0.55);
    background: linear-gradient(135deg, #2786ff, #1264c9);
    color: white;
}

.stButton > button:hover {
    border-color: rgba(113, 188, 255, 0.95);
    background: linear-gradient(135deg, #3a92ff, #1772de);
}

[data-testid="stPydeckChart"] {
    border-radius: 15px;
    overflow: hidden;
    border: 1px solid var(--border);
    box-shadow: 0 20px 44px rgba(0,0,0,0.22);
}

div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
    background: #081522;
}

hr {
    border-color: rgba(255,255,255,0.08);
}

[data-testid="stAlert"] {
    border-radius: 12px;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# CACHE
# =========================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_weather_data(nx: int, ny: int) -> dict:
    return build_weather_data(nx, ny)


# =========================================================
# GEO
# =========================================================

def get_dong_grid(
    roads: gpd.GeoDataFrame,
    dong_name: str,
) -> tuple[int, int]:

    selected_roads = roads[
        roads["ADM_NM"] == dong_name
    ].copy()

    if selected_roads.empty:
        raise ValueError(
            f"{dong_name}에 해당하는 도로가 없습니다."
        )

    selected_roads_m = selected_roads.to_crs(
        epsg=5186
    )

    center_m = (
        selected_roads_m
        .geometry
        .union_all()
        .centroid
    )

    center_wgs84 = (
        gpd.GeoSeries(
            [center_m],
            crs="EPSG:5186",
        )
        .to_crs(epsg=4326)
        .iloc[0]
    )

    return latlon_to_grid(
        latitude=center_wgs84.y,
        longitude=center_wgs84.x,
    )


# =========================================================
# UI HELPERS
# =========================================================

def kpi_card(
    icon: str,
    icon_class: str,
    label: str,
    value: str,
    sub: str,
    color_class: str = "",
):
    html = (
        '<div class="kpi-card">'
        '<div class="kpi-top">'
        f'<div class="kpi-icon {icon_class}">{icon}</div>'
        f'<div class="kpi-label">{label}</div>'
        '</div>'
        f'<div class="kpi-value {color_class}">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def weather_card(
    icon: str,
    icon_class: str,
    label: str,
    value: str,
):
    html = (
        '<div class="weather-card">'
        '<div class="weather-top">'
        f'<div class="weather-icon-box {icon_class}">{icon}</div>'
        f'<div class="weather-label">{label}</div>'
        '</div>'
        f'<div class="weather-value">{value}</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def show_risk_legend():
    html = (
        '<div class="legend-panel">'
        '<div class="legend-wrap">'
        '<span class="legend-title">도로 결빙 위험도 범례</span>'
        '<span class="legend-item"><span class="legend-line" style="background:#10b865"></span>0–20 매우 낮음</span>'
        '<span class="legend-item"><span class="legend-line" style="background:#84c83e"></span>20–40 낮음</span>'
        '<span class="legend-item"><span class="legend-line" style="background:#ffd438"></span>40–60 관심</span>'
        '<span class="legend-item"><span class="legend-line" style="background:#ff9d39"></span>60–80 주의</span>'
        '<span class="legend-item"><span class="legend-line" style="background:#ff2938"></span>80–100 위험</span>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def risk_color_class(level: str) -> str:
    level_text = str(level)

    if (
        "위험" in level_text
        or "경고" in level_text
    ):
        return "v-red"

    if (
        "주의" in level_text
        or "관심" in level_text
    ):
        return "v-yellow"

    return "v-green"


def show_top_kpis(
    target_roads: gpd.GeoDataFrame,
    selected_dong: str,
    simulation_mode: bool,
):
    avg_score = float(
        target_roads["final_score"].mean()
    )

    danger_count = int(
        (
            target_roads["final_score"] >= 80
        ).sum()
    )

    caution_count = int(
        (
            target_roads["final_score"] >= 60
        ).sum()
    )

    overall = classify_risk(
        avg_score
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        kpi_card(
            "🧊",
            "icon-green",
            "현재 위험도",
            overall,
            f"평균 {avg_score:.1f}점",
            risk_color_class(overall),
        )

    with c2:
        kpi_card(
            "🚨",
            "icon-red",
            "고위험 도로",
            f"{danger_count:,}개",
            "위험도 80점 이상",
            "v-red",
        )

    with c3:
        kpi_card(
            "⚠️",
            "icon-yellow",
            "주의 이상 도로",
            f"{caution_count:,}개",
            "위험도 60점 이상",
            "v-yellow",
        )

    with c4:
        kpi_card(
            "📍",
            "icon-purple",
            "분석 지역",
            selected_dong,
            "선택 행정동",
        )

    with c5:
        kpi_card(
            "📡",
            "icon-blue",
            "분석 모드",
            "WINTER" if simulation_mode else "LIVE",
            "겨울 시뮬레이션" if simulation_mode else "실시간 분석",
            "v-blue",
        )


def show_weather_cards(weather: dict):
    st.markdown(
        '<div class="section-title">☁ 현재 기상</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        weather_card(
            "🌡️",
            "icon-red",
            "기온",
            f"{weather['air_temp']:.1f} ℃",
        )

    with c2:
        weather_card(
            "💧",
            "icon-blue",
            "습도",
            f"{weather['humidity']:.0f} %",
        )

    with c3:
        weather_card(
            "💨",
            "icon-blue",
            "풍속",
            f"{weather['wind_speed']:.1f} m/s",
        )

    with c4:
        weather_card(
            "🌧️",
            "icon-purple",
            "강수량",
            f"{weather['rain']:.1f} mm",
        )


def show_result_cards(
    selected_dong: str,
    summary: dict,
):
    left, right = st.columns(
        [1.05, 0.95]
    )

    with left:
        result_html = (
            '<div class="result-card">'
            '<div class="result-title">📋 분석 결과</div>'
            f'<div class="result-main">{selected_dong} 종합 위험도: '
            f'<span class="{risk_color_class(summary["overall"])}">{summary["overall"]}</span></div>'
            '<div class="result-label">평균 위험점수</div>'
            f'<div class="result-value">{summary["avg_score"]}점</div>'
            '<div class="result-label">최대 위험점수</div>'
            f'<div class="result-value">{summary["max_score"]}점</div>'
            '</div>'
        )

        st.markdown(
            result_html,
            unsafe_allow_html=True,
        )

    with right:
        recommendations = "".join(
            f'<div style="color:#dbe6f2;margin-bottom:0.65rem;">• {item}</div>'
            for item in summary["recommendations"]
        )

        recommendation_html = (
            '<div class="result-card">'
            '<div class="result-title">🚧 권장 조치</div>'
            f'{recommendations}'
            '</div>'
        )

        st.markdown(
            recommendation_html,
            unsafe_allow_html=True,
        )


# =========================================================
# DATA
# =========================================================

roads, bridge_geo, tunnel_geo = load_data()

building_shadow_timeseries = (
    load_building_shadow_timeseries()
)

shadow_time_options = sorted(
    building_shadow_timeseries["time"]
    .dropna()
    .unique()
    .tolist()
)

# 결빙 위험 분석은 하루 전체를 대상으로 한다.
# 현재 구축된 일조 음영 자료는 09:00~15:00 구간에서만
# 선택적으로 적용한다.
analysis_time_options = [
    f"{hour:02d}:{minute:02d}"
    for hour in range(24)
    for minute in (0, 30)
]

dong_list = sorted(
    roads["ADM_NM"]
    .dropna()
    .unique()
)


# =========================================================
# SESSION
# =========================================================

if "calculated" not in st.session_state:
    st.session_state.calculated = False


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ❄️ AI Smart De-Ice")
    st.caption("AI 기반 선제적 정밀 제설 의사결정 시스템")

    st.divider()

    st.markdown("### 📍 분석 지역")

    selected_dong = st.selectbox(
        "행정동",
        dong_list,
        index=0,
        placeholder="동 이름을 입력하거나 선택하세요",
        label_visibility="collapsed",
        help="선택박스를 연 뒤 동 이름을 입력하면 일치하는 행정동이 자동으로 검색됩니다.",
    )

    st.markdown("### 🧪 분석 모드")

    simulation_mode = st.toggle(
        "겨울 시뮬레이션",
        value=False,
    )

    if simulation_mode:
        st.caption(
            "동절기 조건을 직접 입력하여 위험도를 분석합니다."
        )
    else:
        st.caption(
            "현재 기상 관측정보를 사용하여 분석합니다."
        )

    st.markdown("### 🕒 분석 기준 시간")

    current_time = datetime.now(KST)
    default_analysis_time = (
        f"{current_time.hour:02d}:"
        f"{'30' if current_time.minute >= 30 else '00'}"
    )

    analysis_shadow_time = st.select_slider(
        "결빙 위험 분석 기준 시간",
        options=analysis_time_options,
        value=default_analysis_time,
        label_visibility="collapsed",
        help=(
            "선택한 시각을 기상 조건과 결빙 위험의 "
            "분석 기준으로 사용합니다. 09:00~15:00에는 "
            "같은 시각의 일조 음영 자료도 적용합니다."
        ),
    )

    if analysis_shadow_time in shadow_time_options:
        st.caption(
            f"☀️ {analysis_shadow_time}의 건물·지형 일조 음영을 반영합니다."
        )
    else:
        st.caption(
            f"🌙 {analysis_shadow_time}은 비일조 분석 시간입니다. "
            "시간별 일조 음영은 적용하지 않습니다."
        )

    st.divider()


# =========================================================
# HERO
# =========================================================

analysis_time = datetime.now(KST).strftime(
    "%Y.%m.%d %H:%M"
)

st.markdown(
    (
        '<div class="hero-row">'
        '<div>'
        '<div class="hero-title">❄️ 블랙아이스 위험도 분석</div>'
        '<div class="hero-subtitle">'
        '실시간 기상 · 도로 지형 · 시설 · 음영 정보를 종합하여 '
        '도로 결빙 위험을 시각화합니다.'
        '</div>'
        '</div>'
        '<div class="update-box">'
        '◷ 마지막 분석 시각<br>'
        f'<b style="color:#edf5fd;">{analysis_time}</b>'
        '</div>'
        '</div>'
    ),
    unsafe_allow_html=True,
)


# =========================================================
# WEATHER INPUT
# =========================================================

weather = None
simulation_submit = False

try:

    nx, ny = get_dong_grid(
        roads,
        selected_dong,
    )

    if simulation_mode:

        with st.sidebar:

            with st.form(
                "winter_simulation_form"
            ):

                st.markdown("### 🌨 시뮬레이션 조건")

                sim_air_temp = st.number_input(
                    "기온 (℃)",
                    value=-1.0,
                    step=0.5,
                )

                sim_humidity = st.number_input(
                    "습도 (%)",
                    min_value=1.0,
                    max_value=100.0,
                    value=95.0,
                    step=1.0,
                )

                sim_rain = st.number_input(
                    "강수량 (mm)",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                )

                sim_wind = st.number_input(
                    "풍속 (m/s)",
                    min_value=0.0,
                    value=3.0,
                    step=0.5,
                )

                st.divider()

                simulation_submit = (
                    st.form_submit_button(
                        "▶ 위험도 분석 실행",
                        type="primary",
                        use_container_width=True,
                    )
                )

        sim_surface_temp = (
            estimate_surface_temperature(
                sim_air_temp
            )
        )

        sim_dew_point = (
            estimate_dew_point(
                sim_air_temp,
                sim_humidity,
            )
        )

        weather = {
            "air_temp": sim_air_temp,
            "humidity": sim_humidity,
            "rain": sim_rain,
            "wind_speed": sim_wind,
            "surface_temp": sim_surface_temp,
            "dew_point": sim_dew_point,
            "nx": nx,
            "ny": ny,
            "base_date": "SIMULATION",
            "base_time": "WINTER",
        }

    else:

        with st.spinner(
            f"{selected_dong} 기상정보를 불러오는 중..."
        ):
            weather = load_weather_data(
                nx,
                ny,
            )

except Exception as error:

    st.error(
        f"{selected_dong} 기상정보를 불러오지 못했습니다: {error}"
    )


# =========================================================
# RUN BUTTON
# =========================================================

with st.sidebar:

    if simulation_mode:

        run_button = simulation_submit

    else:

        st.divider()

        run_button = st.button(
            "▶ 위험도 분석 실행",
            disabled=weather is None,
            type="primary",
        )

    if run_button:
        st.session_state.calculated = True

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        (
            '<div class="sidebar-source">'
            '<b style="color:#d7e4f1;">ⓘ 데이터 출처</b><br><br>'
            '기상청 · 도로/공간정보 데이터<br>'
            '(실시간 연동 및 사전 구축 자료)'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


# =========================================================
# RESULT
# =========================================================

if (
    st.session_state.calculated
    and weather is not None
):

    has_solar_shadow_data = (
        analysis_shadow_time in shadow_time_options
    )

    weather_score, detail = calculate_weather_score(
        weather["air_temp"],
        weather["surface_temp"],
        weather["dew_point"],
        weather["wind_speed"],
        weather["rain"],
    )

    target_roads = roads[
        roads["ADM_NM"] == selected_dong
    ].copy()

    selected_time_shadow = (
        building_shadow_timeseries[
            building_shadow_timeseries["time"]
            == analysis_shadow_time
        ][
            [
                "LINK_ID",
                "building_shadow_ratio",
            ]
        ]
        .rename(
            columns={
                "building_shadow_ratio": (
                    "building_shadow_ratio_current"
                )
            }
        )
    )

    target_roads = target_roads.merge(
        selected_time_shadow,
        on="LINK_ID",
        how="left",
        validate="one_to_one",
    )

    target_roads[
        "building_shadow_ratio_current"
    ] = (
        target_roads[
            "building_shadow_ratio_current"
        ]
        .fillna(0.0)
    )

    # 기존 누적 통합 음영률은 비교·확인용으로 보존한다.
    target_roads[
        "combined_shadow_ratio_aggregate"
    ] = target_roads["combined_shadow_ratio"]

    # 09:00~15:00에는 시간별 건물 음영률과 기존 지형
    # 음영률을 사용한다. 그 밖의 시간에는 낮 시간의
    # 일조 음영을 잘못 재사용하지 않도록 둘 다 0으로 둔다.
    if has_solar_shadow_data:
        terrain_shadow_current = (
            target_roads["terrain_shadow_ratio"]
            .fillna(0.0)
            .clip(lower=0.0, upper=1.0)
        )
    else:
        terrain_shadow_current = (
            target_roads["terrain_shadow_ratio"]
            .fillna(0.0)
            .mul(0.0)
        )

    target_roads[
        "terrain_shadow_ratio_current"
    ] = terrain_shadow_current

    building_shadow_current = (
        target_roads[
            "building_shadow_ratio_current"
        ]
        .clip(lower=0.0, upper=1.0)
    )

    target_roads["combined_shadow_ratio"] = (
        1.0
        - (
            (1.0 - terrain_shadow_current)
            * (1.0 - building_shadow_current)
        )
    ).clip(lower=0.0, upper=1.0)

    target_roads["analysis_shadow_time"] = (
        analysis_shadow_time
    )

    target_roads["solar_shadow_available"] = (
        has_solar_shadow_data
    )

    target_roads = calculate_location_weight(
        target_roads
    )

    target_roads = calculate_final_score(
        target_roads,
        weather_score,
    )

    target_roads["risk_level"] = (
        target_roads["final_score"]
        .apply(classify_risk)
    )

    summary = generate_ai_summary(
        selected_dong,
        weather_score,
        detail,
        target_roads,
    )

    show_top_kpis(
        target_roads,
        selected_dong,
        simulation_mode,
    )

    show_risk_legend()

    show_3d_map(
        target_roads
    )

    show_weather_cards(
        weather
    )

    st.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    show_result_cards(
        selected_dong,
        summary,
    )

    st.markdown(
        '<div class="footer-note">'
        '※ 위 분석 결과는 기상 및 환경 조건 변화에 따라 달라질 수 있습니다.'
        '</div>',
        unsafe_allow_html=True,
    )


elif weather is not None:

    show_weather_cards(
        weather
    )

    st.info(
        "왼쪽에서 분석 지역과 조건을 설정한 뒤 "
        "**위험도 분석 실행**을 눌러주세요."
    )

import math

import geopandas as gpd
import pydeck as pdk
import streamlit as st


# =========================================================
# 기본 설정
# =========================================================

BUILDING_PATH = "data/buildings_final.gpkg"
BUILDING_LAYER = "buildings"
DONG_BOUNDARY_PATH = "data/dong_boundary.geojson"

# 선택 행정동 주변 표시 여유 범위
BUILDING_MARGIN_M = 300

# 지도 표시용으로 고정 타일 경계에서 분할·통합한
# 겹침 없는 연속 건물 그림자
SHADOW_PATH = (
    "data/building_shadow_display_partitioned.gpkg"
)

# Streamlit 캐시가 이전 표시 자료와 섞이지 않도록
# 표시 데이터 버전을 명시한다.
SHADOW_DATA_VERSION = "partitioned_v1"

SHADOW_TIMES = [
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",    
    "13:30",
    "14:00",
    "14:30",
    "15:00",
]


# =========================================================
# 행정동 경계 데이터 로딩
# =========================================================

@st.cache_data(show_spinner=False)
def load_dong_boundary(
    dong_name: str,
):
    """
    선택한 행정동의 실제 경계를 불러온다.

    그림자는 주변 건물이 만드는 부분까지 먼저 읽은 뒤,
    지도 표시 직전에 이 경계 안쪽만 남긴다.
    """

    boundaries = gpd.read_file(
        DONG_BOUNDARY_PATH,
    )

    if "ADM_NM" not in boundaries.columns:
        raise ValueError(
            "행정동 경계 파일에 ADM_NM 컬럼이 없습니다."
        )

    selected_boundary = boundaries[
        boundaries["ADM_NM"].astype(str) == str(dong_name)
    ][["geometry"]].copy()

    if selected_boundary.empty:
        raise ValueError(
            f"{dong_name}의 행정동 경계를 찾지 못했습니다."
        )

    return selected_boundary

# =========================================================
# 건물 그림자 데이터 로딩
# =========================================================

@st.cache_data(show_spinner=False)
def load_buildings_3d(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
):
    """
    선택 행정동 주변 bbox의 건물만 불러온다.
    """

    buildings = gpd.read_file(
        BUILDING_PATH,
        layer=BUILDING_LAYER,
        bbox=(
            minx,
            miny,
            maxx,
            maxy,
        ),
    )

    if buildings.empty:
        return buildings

    buildings["building_height"] = (
        buildings["building_height"]
        .fillna(3.0)
        .clip(
            lower=1.0,
            upper=250.0,
        )
    )

    # 지도에 필요한 정보만 유지
    buildings = buildings[
        [
            "building_height",
            "geometry",
        ]
    ].copy()

    return buildings.to_crs(
        epsg=4326
    )

# =========================================================
# 3D 건물 데이터 로딩
# =========================================================

@st.cache_data(show_spinner=False)
def load_building_shadow(
    shadow_time: str,
    dong_name: str,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    data_version: str,
):
    """
    선택 시간 + 선택 지역 주변의
    건물 그림자만 불러온다.

    지도 표시에는 geometry만 필요하므로
    불필요한 속성 컬럼은 제거한다.
    """

    # data_version은 캐시 구분용 인자다.
    _ = data_version

    layer_name = (
        "display_"
        + shadow_time.replace(":", "")
    )

    shadows = gpd.read_file(
        SHADOW_PATH,
        layer=layer_name,
        bbox=(
            minx,
            miny,
            maxx,
            maxy,
        ),
    )

    if shadows.empty:
        return shadows

    # 지도에 필요한 geometry만 유지
    shadows = shadows[
        [
            "geometry",
        ]
    ].copy()

    # 주변 건물이 선택 행정동 안으로 드리우는 그림자는
    # 유지하되, 행정동 경계 밖에 보이는 부분만 잘라낸다.
    dong_boundary = load_dong_boundary(
        dong_name,
    )

    if dong_boundary.crs != shadows.crs:
        dong_boundary = dong_boundary.to_crs(
            shadows.crs
        )

    boundary_geometry = (
        dong_boundary.geometry.union_all()
    )

    shadows["geometry"] = (
        shadows.geometry.intersection(
            boundary_geometry
        )
    )

    shadows = shadows[
        shadows.geometry.notna()
        & ~shadows.geometry.is_empty
    ].copy()

    if shadows.empty:
        return shadows

    # PyDeck용 좌표계 변환
    shadows = shadows.to_crs(
        epsg=4326
    )

    return shadows

# =========================================================
# 위험도 색상
# =========================================================

def risk_rgb(score):
    """
    도로 위험점수를 RGB 색상으로 변환한다.
    """

    if score < 20:
        return [16, 184, 101]

    elif score < 40:
        return [132, 200, 62]

    elif score < 60:
        return [255, 212, 56]

    elif score < 80:
        return [255, 157, 57]

    elif score < 100:
        return [255, 41, 56]

    else:
        return [150, 0, 20]


def calculate_boundary_zoom(
    boundary_m: gpd.GeoDataFrame,
) -> float:
    """
    행정동 전체 경계가 지도 안에 들어오도록
    경계의 실제 크기에 따라 확대 수준을 계산한다.
    """

    minx, miny, maxx, maxy = (
        boundary_m.total_bounds
    )

    width_m = max(float(maxx - minx), 1.0)
    height_m = max(float(maxy - miny), 1.0)

    # 현재 대시보드의 넓은 지도 비율과 3D pitch를 고려한
    # 보수적인 화면 가용 크기다.
    required_meters_per_pixel = max(
        width_m / 1100.0,
        height_m / 420.0,
        1.0,
    )

    zoom = (
        math.log2(
            126000.0 / required_meters_per_pixel
        )
        - 0.25
    )

    return max(
        10.5,
        min(15.2, zoom),
    )


def build_boundary_paths(
    boundary_wgs84: gpd.GeoDataFrame,
) -> list[dict]:
    """
    행정동 폴리곤 외곽선을 PyDeck PathLayer가
    직접 그릴 수 있는 좌표 목록으로 변환한다.
    """

    boundary_geometry = (
        boundary_wgs84.geometry
        .union_all()
        .boundary
    )

    paths = []

    def collect_line(geometry):
        if geometry is None or geometry.is_empty:
            return

        if geometry.geom_type in {
            "LineString",
            "LinearRing",
        }:
            coordinates = [
                [float(x), float(y)]
                for x, y in geometry.coords
            ]

            if len(coordinates) >= 2:
                paths.append(
                    {"path": coordinates}
                )

            return

        if hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                collect_line(part)

    collect_line(boundary_geometry)

    return paths


# =========================================================
# 3D 지도
# =========================================================

@st.fragment
def show_3d_map(
    target_roads: gpd.GeoDataFrame,
):
    """
    선택 행정동의

    - 위험도 도로
    - 선택 시 3D 건물
    - 선택 시 건물 그림자

    를 하나의 PyDeck 지도에 표시한다.
    """

    # 선택 행정동 이름
    dong_name = str(
        target_roads["ADM_NM"]
        .dropna()
        .iloc[0]
    )

    # -----------------------------------------------------
    # 상단 제목 + 시각화 레이어 컨트롤
    # -----------------------------------------------------

    title_col, building_col, shadow_col = st.columns(
        [1.35, 0.55, 0.65]
    )

    with title_col:

        st.markdown(
            "### 🏙️ 3D 건물 및 도로 시각화"
        )

    with building_col:

        show_buildings = st.toggle(
            "🏢 3D 건물",
            value=True,
            key="map_3d_show_buildings",
            help="지도에서 3D 건물 레이어를 표시합니다.",
        )

    with shadow_col:

        show_shadow = st.toggle(
            "🌥️ 일조 음영",
            value=False,
            key="map_3d_show_shadow",
            help=(
                "겨울철 건물에 의해 형성되는 "
                "시간대별 그림자를 표시합니다."
            ),
        )

    # -----------------------------------------------------
    # 분석 기준 시간
    #
    # 시간 선택은 사이드바에서 한 번만 수행한다.
    # 지도에서는 같은 시간의 그림자를 표시만 한다.
    # -----------------------------------------------------

    selected_time = "-"
    shadow_time = None

    if (
        not target_roads.empty
        and "analysis_shadow_time" in target_roads.columns
    ):
        selected_time = str(
            target_roads[
                "analysis_shadow_time"
            ].iloc[0]
        )

        if selected_time in SHADOW_TIMES:
            shadow_time = selected_time

    if show_shadow and shadow_time is not None:
        st.caption(
            f"☀️ {shadow_time} 기준 건물 그림자를 표시합니다."
        )

    elif show_shadow:
        st.caption(
            "🌙 선택 시간에는 일조 음영 레이어를 적용하지 않습니다."
        )

    # -----------------------------------------------------
    # 선택 지역 범위
    # -----------------------------------------------------

    target_m = target_roads.to_crs(
        epsg=5179
    )

    minx, miny, maxx, maxy = (
        target_m.total_bounds
    )

    bbox_minx = round(
        minx - BUILDING_MARGIN_M,
        1,
    )

    bbox_miny = round(
        miny - BUILDING_MARGIN_M,
        1,
    )

    bbox_maxx = round(
        maxx + BUILDING_MARGIN_M,
        1,
    )

    bbox_maxy = round(
        maxy + BUILDING_MARGIN_M,
        1,
    )

    # -----------------------------------------------------
    # 건물 데이터
    # -----------------------------------------------------

    buildings_view = None

    if show_buildings:

        with st.spinner(
            "3D 건물을 준비하는 중입니다..."
        ):

            buildings_view = load_buildings_3d(
                bbox_minx,
                bbox_miny,
                bbox_maxx,
                bbox_maxy,
            )

    # -----------------------------------------------------
    # 그림자 데이터
    #
    # 체크한 경우에만 읽는다.
    # -----------------------------------------------------

    shadows_view = None

    if (
        show_shadow
        and shadow_time is not None
    ):

        shadows_view = load_building_shadow(
            shadow_time,
            dong_name,
            bbox_minx,
            bbox_miny,
            bbox_maxx,
            bbox_maxy,
            SHADOW_DATA_VERSION,
        )

    # -----------------------------------------------------
    # 도로 좌표계 변환
    # -----------------------------------------------------

    target_wgs84 = target_roads.to_crs(
        epsg=4326
    )

    # 선택한 행정동의 실제 경계를 지도에 표시한다.
    # 행정동을 변경하면 같은 함수가 새 경계를 자동으로 불러온다.
    dong_boundary_m = (
        load_dong_boundary(dong_name)
        .to_crs(epsg=5179)
    )

    dong_boundary_view = (
        dong_boundary_m.to_crs(epsg=4326)
    )

    dong_boundary_paths = build_boundary_paths(
        dong_boundary_view
    )

    if not dong_boundary_paths:
        raise ValueError(
            f"{dong_name} 행정동 경계선을 생성하지 못했습니다."
        )

    # -----------------------------------------------------
    # 레이어 목록
    # -----------------------------------------------------

    layers = []

    # -----------------------------------------------------
    # 그림자 레이어
    #
    # 가장 아래에 깔린다.
    # -----------------------------------------------------

    if (
        show_shadow
        and shadows_view is not None
        and not shadows_view.empty
    ):

        shadow_layer = pdk.Layer(
            "GeoJsonLayer",
            shadows_view,

            filled=True,
            stroked=False,

            get_fill_color=[
                72,
                58,
                110,
                60,
            ],

            extruded=False,

            pickable=False,
        )

        layers.append(
            shadow_layer
        )

    # -----------------------------------------------------
    # 3D 건물 레이어
    # -----------------------------------------------------

    if (
        show_buildings
        and buildings_view is not None
        and not buildings_view.empty
    ):

        building_layer = pdk.Layer(
            "GeoJsonLayer",
            buildings_view,

            filled=True,
            stroked=True,

            get_fill_color=[
                175,
                178,
                184,
                165,
            ],

            get_line_color=[
                90,
                95,
                105,
            ],

            line_width_min_pixels=0.4,

            extruded=True,

            get_elevation="building_height",

            elevation_scale=1,

            # 도로 툴팁 선택을 방해하지 않도록
            # 건물은 시각화 전용으로 사용한다.
            pickable=False,

            auto_highlight=False,
        )

        layers.append(
            building_layer
        )

    # -----------------------------------------------------
    # 위험도 도로 레이어
    # -----------------------------------------------------

    roads_3d = target_wgs84.copy()

    roads_3d["risk_rgb"] = (
        roads_3d["final_score"]
        .apply(risk_rgb)
    )

    roads_3d["final_score_display"] = (
        roads_3d["final_score"]
        .fillna(0.0)
        .map(lambda value: f"{float(value):.1f}점")
    )

    if "risk_level" in roads_3d.columns:
        roads_3d["risk_level_display"] = (
            roads_3d["risk_level"]
            .fillna("미분류")
            .astype(str)
        )
    else:
        roads_3d["risk_level_display"] = "미분류"

    if "analysis_shadow_time" in roads_3d.columns:
        roads_3d["analysis_time_display"] = (
            roads_3d["analysis_shadow_time"]
            .fillna(selected_time)
            .astype(str)
        )
    else:
        roads_3d["analysis_time_display"] = selected_time

    percent_columns = {
        "building_shadow_ratio_current": (
            "building_shadow_percent_display"
        ),
        "terrain_shadow_ratio_current": (
            "terrain_shadow_percent_display"
        ),
        "combined_shadow_ratio": (
            "combined_shadow_percent_display"
        ),
    }

    for source_column, display_column in (
        percent_columns.items()
    ):
        if source_column in roads_3d.columns:
            roads_3d[display_column] = (
                roads_3d[source_column]
                .fillna(0.0)
                .clip(lower=0.0, upper=1.0)
                .mul(100.0)
                .map(lambda value: f"{float(value):.1f}%")
            )
        else:
            roads_3d[display_column] = "-"

    # 건물과 밝은 배경 위에서도 위험도 색상을 식별할 수 있도록
    # 얇은 남색 받침선을 먼저 그리고, 위험도 본선을 그 위에 올린다.
    # depthTest를 끄면 3D 건물에 도로 색상이 가려지지 않는다.
    road_halo_layer = pdk.Layer(
        "GeoJsonLayer",
        roads_3d,

        id="risk-road-halo-v1",

        stroked=True,
        filled=False,

        get_line_color=[
            8,
            24,
            40,
            190,
        ],

        line_width_min_pixels=5.2,

        pickable=False,
        auto_highlight=False,

        parameters={
            "depthTest": False,
        },
    )

    layers.append(
        road_halo_layer
    )

    road_layer = pdk.Layer(
        "GeoJsonLayer",
        roads_3d,

        id="risk-road-main-v2",

        stroked=True,
        filled=False,

        get_line_color="risk_rgb",

        line_width_min_pixels=3.2,

        pickable=True,

        auto_highlight=True,

        highlight_color=[
            255,
            255,
            255,
            90,
        ],

        parameters={
            "depthTest": False,
        },
    )

    layers.append(
        road_layer
    )

    # -----------------------------------------------------
    # 선택 행정동 경계 레이어
    # -----------------------------------------------------

    # GeoJsonLayer의 폴리곤 외곽선 대신 실제 경계 좌표를
    # PathLayer로 직접 그린다. 선명한 전기 파란색 빛과
    # 가는 형광 하늘색 본선을 겹쳐 경계를 확실히 표시한다.
    dong_boundary_halo_layer = pdk.Layer(
        "PathLayer",
        dong_boundary_paths,

        id="selected-dong-boundary-glow-v3",

        get_path="path",

        get_color=[
            0,
            105,
            255,
            225,
        ],

        get_width=1,
        width_min_pixels=4,
        width_max_pixels=4,

        joint_rounded=True,
        cap_rounded=True,
        billboard=True,

        pickable=False,

        parameters={
            "depthTest": False,
        },
    )

    layers.append(
        dong_boundary_halo_layer
    )

    dong_boundary_line_layer = pdk.Layer(
        "PathLayer",
        dong_boundary_paths,

        id="selected-dong-boundary-line-v3",

        get_path="path",

        get_color=[
            80,
            245,
            255,
            255,
        ],

        get_width=1,
        width_min_pixels=2,
        width_max_pixels=2,

        joint_rounded=True,
        cap_rounded=True,
        billboard=True,

        pickable=False,

        parameters={
            "depthTest": False,
        },
    )

    layers.append(
        dong_boundary_line_layer
    )

    # -----------------------------------------------------
    # 지도 중심
    # -----------------------------------------------------

    center = (
        dong_boundary_view
        .geometry
        .union_all()
        .centroid
    )

    boundary_zoom = calculate_boundary_zoom(
        dong_boundary_m
    )

    # -----------------------------------------------------
    # 카메라
    # -----------------------------------------------------

    view_state = pdk.ViewState(
        latitude=center.y,
        longitude=center.x,

        zoom=boundary_zoom,

        pitch=50,

        bearing=0,
    )

    # -----------------------------------------------------
    # 최종 지도
    # -----------------------------------------------------

    deck = pdk.Deck(
        layers=layers,

        initial_view_state=view_state,

        map_style=(
            "https://basemaps.cartocdn.com/"
            "gl/voyager-gl-style/style.json"
        ),

        tooltip={
            "html": """
            <div style="min-width: 220px;">
                <b style="font-size: 14px; color: #ffffff;">
                    도로 LINK {LINK_ID}
                </b>
                <hr style="margin: 7px 0; opacity: 0.25;"/>
                <b>위험 등급:</b> {risk_level_display}<br/>
                <b>최종 위험도:</b> {final_score_display}<br/>
                <b>분석 시간:</b> {analysis_time_display}<br/>
                <b>건물 음영률:</b> {building_shadow_percent_display}<br/>
                <b>지형 음영률:</b> {terrain_shadow_percent_display}<br/>
                <b>통합 음영률:</b> {combined_shadow_percent_display}
            </div>
            """,
            "style": {
                "backgroundColor": "#111827",
                "color": "#e5edf5",
                "fontSize": "12px",
                "padding": "10px 12px",
                "border": "1px solid #334155",
                "borderRadius": "8px",
            },
        },
    )

    st.pydeck_chart(
        deck,
        use_container_width=True,
    )

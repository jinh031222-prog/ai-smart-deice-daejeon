import streamlit as st
import pandas as pd
import geopandas as gpd


# =========================================================
# 기본 설정
# =========================================================

FACILITY_SOURCE_CRS = "EPSG:5186"
# bridge/tunnel GeoJSON의 실제 좌표가
# Korea 2000 / Central Belt 미터 좌표인 경우 사용

BUILDING_SHADOW_TIMESERIES_PATH = (
    "data/road_building_shadow_timeseries_continuous.csv"
)


# =========================================================
# 시간별 도로 건물 음영률 읽기
# =========================================================

@st.cache_data(show_spinner=False)
def load_building_shadow_timeseries():
    """
    연속 그림자로 계산한 09:00~15:00 시간별
    도로 LINK 건물 음영률을 읽는다.

    기존 load_data()의 반환값과 동작은 변경하지 않는다.
    위험도 계산에서 분석 시간을 연결할 때 이 함수를 별도로 사용한다.
    """

    timeseries = pd.read_csv(
        BUILDING_SHADOW_TIMESERIES_PATH,
        dtype={"LINK_ID": str},
    )

    required_columns = {
        "LINK_ID",
        "time",
        "building_shadow_ratio",
    }

    missing_columns = (
        required_columns - set(timeseries.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )
        raise ValueError(
            "시간별 건물 음영 파일에 필요한 컬럼이 없습니다: "
            f"{missing_text}"
        )

    timeseries = timeseries[
        [
            "LINK_ID",
            "time",
            "building_shadow_ratio",
        ]
    ].copy()

    timeseries["LINK_ID"] = (
        timeseries["LINK_ID"].astype(str)
    )

    timeseries["time"] = (
        timeseries["time"].astype(str).str.strip()
    )

    timeseries["building_shadow_ratio"] = (
        pd.to_numeric(
            timeseries["building_shadow_ratio"],
            errors="raise",
        )
    )

    return timeseries


# =========================================================
# 교량 / 터널 geometry 읽기
# =========================================================

def _read_facility_geo(path: str, target_crs):
    """
    교량/터널 geometry를 읽고,
    GeoJSON에 CRS가 잘못 지정되어 있는 경우 보정한다.
    """

    gdf = gpd.read_file(path)

    minx, miny, maxx, maxy = gdf.total_bounds

    looks_like_lonlat = (
        (-180 <= minx <= 180)
        and (-180 <= maxx <= 180)
        and (-90 <= miny <= 90)
        and (-90 <= maxy <= 90)
    )

    # 위경도 범위를 벗어나면
    # 실제 좌표는 EPSG:5186 미터 좌표라고 판단
    if not looks_like_lonlat:
        gdf = gdf.set_crs(
            FACILITY_SOURCE_CRS,
            allow_override=True
        )

    return gdf.to_crs(target_crs)


# =========================================================
# 전체 데이터 로딩
# =========================================================

@st.cache_data
def load_data():

    # -----------------------------------------------------
    # 1. 기본 데이터 불러오기
    # -----------------------------------------------------

    roads = gpd.read_file(
        "data/roads.geojson"
    )

    # 도로 경사도
    slope = gpd.read_file(
        "data/daejeon_road_slope.gpkg"
    )

    # 도로별 그림자
    shadow = pd.read_csv(
        "data/road_solar_shadow.csv"
    )

    # 행정동
    road_dong = pd.read_csv(
        "data/road_dong.csv"
    )

    # 교량 / 터널 LINK
    bridge = pd.read_csv(
        "data/bridge_links.csv"
    )

    tunnel = pd.read_csv(
        "data/tunnel_links.csv"
    )


    # -----------------------------------------------------
    # 2. LINK_ID 자료형 통일
    # -----------------------------------------------------

    roads["LINK_ID"] = (
        roads["LINK_ID"].astype(str)
    )

    slope["LINK_ID"] = (
        slope["LINK_ID"].astype(str)
    )

    shadow["LINK_ID"] = (
        shadow["LINK_ID"].astype(str)
    )

    road_dong["LINK_ID"] = (
        road_dong["LINK_ID"].astype(str)
    )

    bridge["LINK_ID"] = (
        bridge["LINK_ID"].astype(str)
    )

    tunnel["LINK_ID"] = (
        tunnel["LINK_ID"].astype(str)
    )


    # -----------------------------------------------------
    # 3. 행정동 정보 결합
    # -----------------------------------------------------

    roads = roads.merge(
        road_dong[
            [
                "LINK_ID",
                "ADM_NM"
            ]
        ],
        on="LINK_ID",
        how="left"
    )


    # -----------------------------------------------------
    # 4. 경사도 정보 결합
    # -----------------------------------------------------

    slope_info = slope[
        [
            "LINK_ID",
            "mean",
            "max"
        ]
    ].copy()

    slope_info = slope_info.rename(
        columns={
            "mean": "slope_mean",
            "max": "slope_max"
        }
    )

    roads = roads.merge(
        slope_info,
        on="LINK_ID",
        how="left"
    )

    # 경사도 값이 없는 LINK 처리
    roads["slope_mean"] = (
        roads["slope_mean"]
        .fillna(0.0)
    )

    roads["slope_max"] = (
        roads["slope_max"]
        .fillna(0.0)
    )


       # -----------------------------------------------------
    # 5. 통합 그림자 정보 결합
    # -----------------------------------------------------

    shadow_info = shadow[
        [
            "LINK_ID",
            "terrain_shadow_ratio",
            "terrain_shadow_max",
            "building_shadow_ratio",
            "building_shadow_mean_hours",
            "building_shadow_max_hours",
            "building_shadow_peak_ratio",
            "combined_shadow_ratio",
        ]
    ].copy()

    roads = roads.merge(
        shadow_info,
        on="LINK_ID",
        how="left"
    )

    # 그림자 값이 없는 LINK가 있을 경우 0으로 처리
    shadow_columns = [
        "terrain_shadow_ratio",
        "terrain_shadow_max",
        "building_shadow_ratio",
        "building_shadow_mean_hours",
        "building_shadow_max_hours",
        "building_shadow_peak_ratio",
        "combined_shadow_ratio",
    ]

    for column in shadow_columns:
        roads[column] = (
            roads[column]
            .fillna(0.0)
        )

    # -----------------------------------------------------
    # 기존 코드 호환용
    # -----------------------------------------------------
    #
    # 예전 코드에서 shadow_mean / shadow_max를
    # 참조하는 부분이 남아 있어도 오류가 나지 않도록
    # 지형 그림자 값을 같은 이름으로 유지한다.
    #

    roads["shadow_mean"] = (
        roads["terrain_shadow_ratio"]
    )

    roads["shadow_max"] = (
        roads["terrain_shadow_max"]
    )

    # -----------------------------------------------------
    # 6. 교량 / 터널 여부
    # -----------------------------------------------------

    bridge_ids = set(
        bridge["LINK_ID"]
    )

    tunnel_ids = set(
        tunnel["LINK_ID"]
    )

    roads["is_bridge"] = (
        roads["LINK_ID"]
        .isin(bridge_ids)
    )

    roads["is_tunnel"] = (
        roads["LINK_ID"]
        .isin(tunnel_ids)
    )


    # -----------------------------------------------------
    # 7. 실제 교량 / 터널 geometry
    # -----------------------------------------------------

    bridge_geo = _read_facility_geo(
        "data/bridge/bridge.geojson",
        roads.crs
    )

    tunnel_geo = _read_facility_geo(
        "data/tunnel/tunnel.geojson",
        roads.crs
    )


    # -----------------------------------------------------
    # 8. 반환
    # -----------------------------------------------------

    return (
        roads,
        bridge_geo,
        tunnel_geo
    )
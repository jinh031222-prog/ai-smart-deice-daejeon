import folium
import geopandas as gpd
from modules.config import *


MAP_FILTER_CRS = "EPSG:5186"  # meter-based CRS for Daejeon spatial filtering/buffering


def get_color(score):
    if score < GREEN_LIMIT:
        return COLOR_GREEN
    elif score < LIGHT_GREEN_LIMIT:
        return COLOR_LIGHT_GREEN
    elif score < YELLOW_LIMIT:
        return COLOR_YELLOW
    elif score < ORANGE_LIMIT:
        return COLOR_ORANGE
    elif score < RED_LIMIT:
        return COLOR_RED
    else:
        return COLOR_DARK_RED


def _filter_facilities_near_roads(facility_geo, target_roads, buffer_m=40):
    """Keep only actual bridge/tunnel geometries that overlap the selected road area."""
    if facility_geo is None or len(facility_geo) == 0 or len(target_roads) == 0:
        return None

    roads_m = target_roads.to_crs(MAP_FILTER_CRS)
    facility_m = facility_geo.to_crs(MAP_FILTER_CRS)

    road_area = roads_m.geometry.buffer(buffer_m).union_all()
    filtered = facility_m[facility_m.geometry.intersects(road_area)].copy()

    if len(filtered) == 0:
        return None

    return filtered.to_crs(target_roads.crs)


def draw_risk_map(target_roads, bridge_geo=None, tunnel_geo=None, weather_score=0):
    map_roads = target_roads.to_crs(epsg=4326)
    center = map_roads.geometry.union_all().centroid

    m = folium.Map(
        location=[center.y, center.x],
        zoom_start=14,
        tiles="CartoDB positron"
    )

    # 도로 LINK는 일반 도로 위험도만 표시한다.
    # 교량/터널이 포함된 LINK라도 전체 LINK를 진하게 칠하지 않는다.
    road_layer = folium.FeatureGroup(name="도로 LINK 기본 위험도", show=True)
    folium.GeoJson(
        map_roads,
        name="도로 LINK 기본 위험도",
        style_function=lambda feature: {
           "color": get_color(feature["properties"]["final_score"]),
           "weight": 5 if feature["properties"]["final_score"] >= ORANGE_LIMIT else 3,
           "opacity": 1.0,
        },
        
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "LINK_ID",
                "ROAD_NAME",
                "ADM_NM",
                "is_bridge",
                "is_tunnel",
                "risk_factor",
                "location_weight",
                "final_score",
                "risk_level"
            ],
            aliases=[
                "LINK_ID",
                "도로명",
                "행정동",
                "교량 LINK",
                "터널 LINK",
                "위험요소",
                "위치가중치",
                "최종점수",
                "위험등급"
            ]
        )
    ).add_to(road_layer)
    road_layer.add_to(m)

    # 실제 교량/터널 geometry 전용 위험도.
    # LINK 전체가 아니라 실제 시설물 선/면만 강하게 표시하기 위한 값이다.
    bridge_score = min(weather_score * BRIDGE_WEIGHT + 15, 150)
    tunnel_score = min(weather_score * TUNNEL_WEIGHT + 25, 150)

    bridge_view = _filter_facilities_near_roads(bridge_geo, target_roads)
    if bridge_view is not None:
        bridge_layer = folium.FeatureGroup(name="교량 실제 geometry", show=True)
        bridge_view = bridge_view.copy()
        bridge_view["structure_score"] = bridge_score
        bridge_view["structure_type"] = "교량"

        folium.GeoJson(
            bridge_view.to_crs(epsg=4326),
            name="교량 실제 geometry",
            style_function=lambda feature: {
                "color": get_color(feature["properties"]["structure_score"]),
                "fillColor": get_color(feature["properties"]["structure_score"]),
                "weight": 7,
                "opacity": 1.0,
                "fillOpacity": 0.65,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[c for c in ["structure_type", "structure_score", "교량명", "교량종류", "총연장", "왕복차로수"] if c in bridge_view.columns],
                aliases=["구분", "시설물 위험점수", "교량명", "교량종류", "총연장", "왕복차로수"][:len([c for c in ["structure_type", "structure_score", "교량명", "교량종류", "총연장", "왕복차로수"] if c in bridge_view.columns])]
            ) if any(c in bridge_view.columns for c in ["structure_type", "structure_score", "교량명", "교량종류", "총연장", "왕복차로수"]) else None
        ).add_to(bridge_layer)
        bridge_layer.add_to(m)

    tunnel_view = _filter_facilities_near_roads(tunnel_geo, target_roads)
    if tunnel_view is not None:
        tunnel_layer = folium.FeatureGroup(name="터널 실제 geometry", show=True)
        tunnel_view = tunnel_view.copy()
        tunnel_view["structure_score"] = tunnel_score
        tunnel_view["structure_type"] = "터널"

        folium.GeoJson(
            tunnel_view.to_crs(epsg=4326),
            name="터널 실제 geometry",
            style_function=lambda feature: {
                "color": get_color(feature["properties"]["structure_score"]),
                "fillColor": get_color(feature["properties"]["structure_score"]),
                "weight": 8,
                "opacity": 1.0,
                "fillOpacity": 0.70,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[c for c in ["structure_type", "structure_score", "터널명", "총연장", "왕복차로수"] if c in tunnel_view.columns],
                aliases=["구분", "시설물 위험점수", "터널명", "총연장", "왕복차로수"][:len([c for c in ["structure_type", "structure_score", "터널명", "총연장", "왕복차로수"] if c in tunnel_view.columns])]
            ) if any(c in tunnel_view.columns for c in ["structure_type", "structure_score", "터널명", "총연장", "왕복차로수"]) else None
        ).add_to(tunnel_layer)
        tunnel_layer.add_to(m)

   
    return m

import math

from modules import config as cfg


# =========================================================
# 공통 보조 함수
# =========================================================

def _parse_time_minutes(analysis_time):
    """
    HH:MM 문자열 또는 datetime/time 객체를
    자정 이후 누적 분으로 변환한다.
    """

    if analysis_time is None:
        return None

    if (
        hasattr(analysis_time, "hour")
        and hasattr(analysis_time, "minute")
    ):
        return (
            int(analysis_time.hour) * 60
            + int(analysis_time.minute)
        )

    try:
        hour_text, minute_text = (
            str(analysis_time).strip().split(":")[:2]
        )
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return None

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return hour * 60 + minute


def is_night_time(analysis_time) -> bool:
    """
    야간 기준: 18:00~다음 날 07:30
    """

    minutes = _parse_time_minutes(
        analysis_time
    )

    if minutes is None:
        return False

    return (
        minutes >= cfg.NIGHT_START_MINUTES
        or minutes <= cfg.NIGHT_END_MINUTES
    )


# =========================================================
# 1. 블랙아이스 결빙 형태 분석
# =========================================================

def analyze_blackice_types(
    air_temp,
    surface_temp,
    dew_point,
    wind_speed,
    rain,
    analysis_time=None,
):
    """
    C1·C2·C3와 보조 조건을 이용해
    현재 가능한 블랙아이스 결빙 형태를 분석한다.

    이 결과는 위험점수에 직접 더하지 않는다.
    """

    air_temp = float(air_temp)
    surface_temp = float(surface_temp)
    dew_point = float(dew_point)
    wind_speed = float(wind_speed)
    rain = float(rain)

    c1 = surface_temp < 0.0
    c2 = c1 and surface_temp < dew_point
    c3 = c1 and air_temp > 0.0

    radiative_cooling = (
        c1
        and is_night_time(analysis_time)
        and rain <= 0.0
        and wind_speed < cfg.RADIATIVE_WIND_LEVEL_1
    )

    precipitation_freezing = (
        c1
        and rain > 0.0
    )

    types = []

    if c1:
        types.append("C1 저온 노면형")

    if c2:
        types.append("C2 응결·서리형")

    if c3:
        types.append("C3 함정형")

    if radiative_cooling:
        types.append("복사냉각형")

    if precipitation_freezing:
        types.append("강수 결빙형")

    if types:
        type_label = " · ".join(types)
    else:
        type_label = "현재 결빙 형태 미충족"

    return {
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "radiative_cooling": radiative_cooling,
        "precipitation_freezing": precipitation_freezing,
        "types": types,
        "type_label": type_label,
    }


# =========================================================
# 2. 기상 위험도
# =========================================================

def _surface_temperature_score(
    surface_temp,
):
    if surface_temp > cfg.SURFACE_TEMP_LEVEL_1:
        return cfg.SURFACE_TEMP_SCORE_0

    if surface_temp > cfg.SURFACE_TEMP_LEVEL_2:
        return cfg.SURFACE_TEMP_SCORE_1

    if surface_temp > cfg.SURFACE_TEMP_LEVEL_3:
        return cfg.SURFACE_TEMP_SCORE_2

    if surface_temp > cfg.SURFACE_TEMP_LEVEL_4:
        return cfg.SURFACE_TEMP_SCORE_3

    return cfg.SURFACE_TEMP_SCORE_4


def _moisture_score(
    surface_temp,
    dew_point,
    rain,
):
    if (
        rain > 0.0
        and surface_temp
        <= cfg.PRECIPITATION_SURFACE_LIMIT
    ):
        return cfg.MOISTURE_SCORE_PRECIPITATION

    dew_spread = (
        surface_temp - dew_point
    )

    if dew_spread <= cfg.DEW_SPREAD_LEVEL_1:
        return cfg.MOISTURE_SCORE_CONDENSATION

    if dew_spread <= cfg.DEW_SPREAD_LEVEL_2:
        return cfg.MOISTURE_SCORE_NEAR_DEW_1

    if dew_spread <= cfg.DEW_SPREAD_LEVEL_3:
        return cfg.MOISTURE_SCORE_NEAR_DEW_2

    return cfg.MOISTURE_SCORE_DRY


def _air_temperature_score(
    air_temp,
):
    if air_temp > cfg.AIR_TEMP_LEVEL_1:
        return cfg.AIR_TEMP_SCORE_0

    if air_temp > cfg.AIR_TEMP_LEVEL_2:
        return cfg.AIR_TEMP_SCORE_1

    if air_temp > cfg.AIR_TEMP_LEVEL_3:
        return cfg.AIR_TEMP_SCORE_2

    return cfg.AIR_TEMP_SCORE_3


def _radiative_cooling_score(
    wind_speed,
    rain,
    analysis_time,
):
    if (
        not is_night_time(analysis_time)
        or rain > 0.0
    ):
        return 0

    if wind_speed < cfg.RADIATIVE_WIND_LEVEL_1:
        return cfg.RADIATIVE_SCORE_STRONG

    if wind_speed < cfg.RADIATIVE_WIND_LEVEL_2:
        return cfg.RADIATIVE_SCORE_MODERATE

    return cfg.RADIATIVE_SCORE_WEAK


def calculate_weather_score(
    air_temp,
    surface_temp,
    dew_point,
    wind_speed,
    rain,
    analysis_time=None,
):
    """
    기상조건으로 기본 결빙 위험점수 W(0~100)를 계산한다.

    analysis_time은 기존 앱 호출과의 호환을 위해 선택 인자다.
    다음 단계에서 앱의 24시간 선택값을 연결하면
    야간 복사냉각 점수가 활성화된다.
    """

    air_temp = float(air_temp)
    surface_temp = float(surface_temp)
    dew_point = float(dew_point)
    wind_speed = float(wind_speed)
    rain = float(rain)

    surface_score = _surface_temperature_score(
        surface_temp
    )

    moisture_score = _moisture_score(
        surface_temp,
        dew_point,
        rain,
    )

    air_score = _air_temperature_score(
        air_temp
    )

    radiative_score = (
        _radiative_cooling_score(
            wind_speed,
            rain,
            analysis_time,
        )
    )

    detail = []

    for name, component_score in [
        ("지면온도", surface_score),
        ("수분 공급", moisture_score),
        ("기온", air_score),
        ("복사냉각", radiative_score),
    ]:
        if component_score > 0:
            detail.append(
                (name, component_score)
            )

    raw_score = (
        surface_score
        + moisture_score
        + air_score
        + radiative_score
    )

    adjusted_score = raw_score

    if surface_temp > cfg.SURFACE_TEMP_LEVEL_1:
        adjusted_score = min(
            adjusted_score,
            cfg.WARM_SURFACE_SCORE_CAP,
        )

    elif surface_temp > cfg.SURFACE_TEMP_LEVEL_2:
        adjusted_score = min(
            adjusted_score,
            cfg.NEAR_FREEZING_SCORE_CAP,
        )

    elif moisture_score == cfg.MOISTURE_SCORE_DRY:
        adjusted_score = min(
            adjusted_score,
            cfg.DRY_CONDITION_SCORE_CAP,
        )

    adjusted_score = min(
        adjusted_score,
        cfg.WEATHER_SCORE_MAX,
    )

    if adjusted_score < raw_score:
        detail.append(
            (
                "온도·수분 상한 보정",
                adjusted_score - raw_score,
            )
        )

    return int(adjusted_score), detail


# =========================================================
# 3. 시간별 음영 가중계수
# =========================================================

def calculate_shadow_factor(
    combined_shadow_ratio,
):
    """
    선택 시간의 건물·지형 통합 음영률을
    해빙·건조 지연 가중계수로 변환한다.
    """

    if combined_shadow_ratio is None:
        return cfg.SHADOW_FACTOR_0

    try:
        ratio = float(
            combined_shadow_ratio
        )
    except (TypeError, ValueError):
        return cfg.SHADOW_FACTOR_0

    if math.isnan(ratio):
        return cfg.SHADOW_FACTOR_0

    if ratio >= cfg.SHADOW_LEVEL_4:
        return cfg.SHADOW_FACTOR_4

    if ratio >= cfg.SHADOW_LEVEL_3:
        return cfg.SHADOW_FACTOR_3

    if ratio >= cfg.SHADOW_LEVEL_2:
        return cfg.SHADOW_FACTOR_2

    if ratio >= cfg.SHADOW_LEVEL_1:
        return cfg.SHADOW_FACTOR_1

    return cfg.SHADOW_FACTOR_0


def calculate_shadow_score(
    combined_shadow_ratio,
):
    """
    기존 화면·요약 코드와의 호환용 값이다.
    새 최종식에서는 가산점이 아니라 shadow_factor를 사용한다.
    """

    factor = calculate_shadow_factor(
        combined_shadow_ratio
    )

    return round(
        (factor - 1.0) * 100.0,
        1,
    )


# =========================================================
# 4. 경사도 운행위험 가중계수
# =========================================================

def calculate_slope_factor(
    slope_max,
):
    if slope_max is None:
        return cfg.SLOPE_FACTOR_0

    try:
        slope_max = float(slope_max)
    except (TypeError, ValueError):
        return cfg.SLOPE_FACTOR_0

    if math.isnan(slope_max):
        return cfg.SLOPE_FACTOR_0

    if slope_max >= cfg.SLOPE_LEVEL_4:
        return cfg.SLOPE_FACTOR_4

    if slope_max >= cfg.SLOPE_LEVEL_3:
        return cfg.SLOPE_FACTOR_3

    if slope_max >= cfg.SLOPE_LEVEL_2:
        return cfg.SLOPE_FACTOR_2

    if slope_max >= cfg.SLOPE_LEVEL_1:
        return cfg.SLOPE_FACTOR_1

    return cfg.SLOPE_FACTOR_0


def calculate_slope_score(
    slope_max,
):
    """
    기존 코드 호환용 표시값이다.
    """

    factor = calculate_slope_factor(
        slope_max
    )

    return round(
        (factor - 1.0) * 100.0,
        1,
    )


# =========================================================
# 5. 교량·터널 시설물 가중계수
# =========================================================

def calculate_location_weight(
    roads,
):
    """
    일반 도로, 교량 포함 LINK, 터널 포함 LINK를 구분하고
    시설물 가중계수를 계산한다.
    """

    roads = roads.copy()

    bridge_mask = (
        roads["is_bridge"]
        .fillna(False)
        .astype(bool)
    )

    tunnel_mask = (
        roads["is_tunnel"]
        .fillna(False)
        .astype(bool)
    )

    roads["location_weight"] = (
        cfg.ROAD_WEIGHT
    )

    roads.loc[
        bridge_mask,
        "location_weight",
    ] *= cfg.BRIDGE_WEIGHT

    roads.loc[
        tunnel_mask,
        "location_weight",
    ] *= cfg.TUNNEL_WEIGHT

    roads["facility_factor"] = (
        roads["location_weight"]
    )

    roads["risk_factor"] = "일반도로"

    roads.loc[
        bridge_mask,
        "risk_factor",
    ] = "교량 포함 LINK"

    roads.loc[
        tunnel_mask,
        "risk_factor",
    ] = "터널 포함 LINK"

    roads.loc[
        bridge_mask & tunnel_mask,
        "risk_factor",
    ] = "교량+터널 포함 LINK"

    return roads


# =========================================================
# 6. 최종 LINK 위험도
# =========================================================

def calculate_final_score(
    roads,
    weather_score,
):
    """
    최종 위험도:

        final_score
        = weather_score × 0.70
          + normalized_spatial_risk × 30
            × weather_activation

    기상조건만으로 모든 도로가 같은 위험등급이 되는 현상을
    줄이고, 음영·시설·경사가 겹친 도로만 높은 점수를 받게 한다.
    기상점수가 낮으면 공간점수도 함께 감소하므로 공간조건만으로
    결빙 위험이 발생하지 않는다.
    """

    roads = roads.copy()

    if "location_weight" not in roads.columns:
        roads = calculate_location_weight(
            roads
        )

    roads["weather_score"] = float(
        weather_score
    )

    roads["icing_score"] = (
        roads["weather_score"]
    )

    roads["shadow_factor"] = (
        roads["combined_shadow_ratio"]
        .apply(calculate_shadow_factor)
    )

    roads["shadow_score"] = (
        roads["combined_shadow_ratio"]
        .apply(calculate_shadow_score)
    )

    roads["slope_factor"] = (
        roads["slope_max"]
        .apply(calculate_slope_factor)
    )

    roads["slope_score"] = (
        roads["slope_max"]
        .apply(calculate_slope_score)
    )

    roads["facility_factor"] = (
        roads["location_weight"]
        .fillna(cfg.ROAD_WEIGHT)
    )

    roads["spatial_factor_raw"] = (
        roads["shadow_factor"]
        * roads["facility_factor"]
        * roads["slope_factor"]
    )

    roads["spatial_factor"] = (
        roads["spatial_factor_raw"]
        .clip(
            lower=1.0,
            upper=cfg.MAX_SPATIAL_FACTOR,
        )
    )

    spatial_factor_range = max(
        cfg.MAX_SPATIAL_FACTOR - 1.0,
        0.000001,
    )

    roads["spatial_risk_index"] = (
        (
            roads["spatial_factor"] - 1.0
        )
        / spatial_factor_range
    ).clip(lower=0.0, upper=1.0)

    roads["weather_activation"] = min(
        max(
            float(weather_score)
            / cfg.SPATIAL_ACTIVATION_REFERENCE,
            0.0,
        ),
        1.0,
    )

    roads["weather_component"] = (
        roads["weather_score"]
        * cfg.WEATHER_COMPONENT_WEIGHT
    )

    roads["spatial_component"] = (
        roads["spatial_risk_index"]
        * cfg.SPATIAL_COMPONENT_MAX
        * roads["weather_activation"]
    )

    roads["final_score"] = (
        roads["weather_component"]
        + roads["spatial_component"]
    )

    roads["final_score"] = (
        roads["final_score"]
        .clip(lower=0.0, upper=100.0)
    )

    # 기존 코드 호환 및 확인용
    roads["location_bonus"] = (
        roads["weather_score"]
        * (
            roads["facility_factor"] - 1.0
        )
    )

    roads["risk_level"] = (
        roads["final_score"]
        .apply(classify_risk)
    )

    return roads


# =========================================================
# 7. 위험등급 분류
# =========================================================

def classify_risk(
    score,
):
    score = float(score)

    if score < cfg.GREEN_LIMIT:
        return "매우 낮음"

    if score < cfg.LIGHT_GREEN_LIMIT:
        return "낮음"

    if score < cfg.YELLOW_LIMIT:
        return "관심"

    if score < cfg.ORANGE_LIMIT:
        return "주의"

    return "위험"


# =========================================================
# 8. 결과 요약
# =========================================================

def generate_ai_summary(
    selected_dong,
    weather_score,
    detail,
    target_roads,
):
    """
    선택 행정동의 위험도와 주요 영향요인을 요약한다.
    """

    avg_score = float(
        target_roads["final_score"].mean()
    )

    max_score = float(
        target_roads["final_score"].max()
    )

    overall = classify_risk(
        avg_score
    )

    bridge_count = int(
        target_roads["is_bridge"].sum()
    )

    tunnel_count = int(
        target_roads["is_tunnel"].sum()
    )

    reasons = []

    for name, component_score in detail:
        if component_score >= 0:
            reasons.append(
                f"{name} 조건으로 기상 위험도 "
                f"+{component_score}점이 반영되었습니다."
            )
        else:
            reasons.append(
                f"{name}으로 기상 위험도가 "
                f"{abs(component_score)}점 조정되었습니다."
            )

    shadow_roads = target_roads[
        target_roads["shadow_factor"] > 1.0
    ]

    if len(shadow_roads) > 0:
        reasons.append(
            f"선택 시간의 건물·지형 음영으로 위험이 "
            f"증가하는 도로 LINK가 {len(shadow_roads)}개 있습니다."
        )

    slope_roads = target_roads[
        target_roads["slope_factor"] > 1.0
    ]

    if len(slope_roads) > 0:
        reasons.append(
            f"경사로 인해 운행위험이 증가하는 도로 LINK가 "
            f"{len(slope_roads)}개 있습니다."
        )

    if bridge_count > 0:
        reasons.append(
            f"교량이 포함된 도로 LINK가 "
            f"{bridge_count}개 있습니다."
        )

    if tunnel_count > 0:
        reasons.append(
            f"터널이 포함된 도로 LINK가 "
            f"{tunnel_count}개 있습니다."
        )

    recommendations = []

    if overall == "위험":
        recommendations.append(
            "고위험 도로를 중심으로 우선 제설과 "
            "현장 순찰이 필요합니다."
        )
        recommendations.append(
            "교량·급경사·장시간 음영 구간에 "
            "감속 안내를 우선 적용해야 합니다."
        )

    elif overall == "주의":
        recommendations.append(
            "급경사 및 음영 취약구간을 중심으로 "
            "사전 점검이 필요합니다."
        )
        recommendations.append(
            "운전자에게 결빙 주의 운행 안내가 필요합니다."
        )

    elif overall == "관심":
        recommendations.append(
            "기온과 노면온도의 추가 하강 여부를 "
            "지속해서 확인해야 합니다."
        )

    else:
        recommendations.append(
            "현재는 낮은 위험 수준이지만 "
            "기상 변화 여부를 확인해야 합니다."
        )

    return {
        "overall": overall,
        "avg_score": round(avg_score, 1),
        "max_score": round(max_score, 1),
        "weather_score": weather_score,
        "reasons": reasons,
        "recommendations": recommendations,
    }


# =========================================================
# 9. 노면온도 추정
# =========================================================

def estimate_surface_temperature(
    air_temp: float,
    offset: float = -2.0,
) -> float:
    """
    현재 임시 프로토콜:
        추정 노면온도 = 기온 - 2℃
    """

    return float(air_temp) + float(offset)


# =========================================================
# 10. 이슬점 추정
# =========================================================

def estimate_dew_point(
    air_temp: float,
    humidity: float,
) -> float:
    """
    기온과 상대습도로 이슬점온도를 추정한다.
    Magnus 공식을 사용한다.
    """

    air_temp = float(air_temp)
    humidity = float(humidity)

    if not (0.0 < humidity <= 100.0):
        raise ValueError(
            "습도는 0보다 크고 100 이하여야 합니다."
        )

    a = 17.62
    b = 243.12

    gamma = (
        math.log(
            humidity / 100.0
        )
        + (
            a * air_temp
        )
        / (
            b + air_temp
        )
    )

    dew_point = (
        b * gamma
    ) / (
        a - gamma
    )

    return round(
        dew_point,
        1,
    )

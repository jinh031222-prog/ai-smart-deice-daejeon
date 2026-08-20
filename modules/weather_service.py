from modules.weather_api import get_current_weather
from modules.risk_engine import (
    estimate_surface_temperature,
    estimate_dew_point,
)


def build_weather_data(nx: int, ny: int) -> dict:
    """기상청 원자료와 계산된 기상 변수를 하나로 묶어 반환한다."""

    current_weather = get_current_weather(nx, ny)

    air_temp = float(current_weather["temperature"])
    humidity = float(current_weather["humidity"])
    rain = float(current_weather["rainfall"])
    wind_speed = float(current_weather["wind_speed"])

    surface_temp = estimate_surface_temperature(air_temp)
    dew_point = estimate_dew_point(air_temp, humidity)

    return {
        "air_temp": air_temp,
        "humidity": humidity,
        "rain": rain,
        "wind_speed": wind_speed,
        "surface_temp": surface_temp,
        "dew_point": dew_point,
        "base_date": current_weather["base_date"],
        "base_time": current_weather["base_time"],
        "nx": nx,
        "ny": ny,
    }
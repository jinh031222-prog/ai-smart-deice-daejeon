import math
import os

from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import requests
from dotenv import load_dotenv


load_dotenv()

# 기상청 API의 기준 시각은 한국 표준시(KST, UTC+9)이다.
# 배포 서버가 UTC를 사용하더라도 요청 시각이 어긋나지 않도록 고정한다.
KST = timezone(timedelta(hours=9))

SERVICE_KEY = unquote(os.getenv("KMA_SERVICE_KEY", ""))

API_URL = (
    "https://apis.data.go.kr/1360000/"
    "VilageFcstInfoService_2.0/getUltraSrtNcst"
)


def get_base_datetime():
    """
    초단기실황은 매시 정각 기준으로 발표되지만,
    API 반영 시간을 고려해 현재 시각보다 40분 전 기준을 사용한다.
    """
    now = datetime.now(KST) - timedelta(minutes=40)

    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")

    return base_date, base_time


def latlon_to_grid(latitude, longitude):
    """
    위도·경도를 기상청 단기예보 격자 좌표(nx, ny)로 변환한다.
    """

    re = 6371.00877
    grid = 5.0
    slat1 = 30.0
    slat2 = 60.0
    olon = 126.0
    olat = 38.0
    xo = 43.0
    yo = 136.0

    degrad = math.pi / 180.0

    re = re / grid
    slat1 = slat1 * degrad
    slat2 = slat2 * degrad
    olon = olon * degrad
    olat = olat * degrad

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5)
    sn = math.log(
        math.cos(slat1) / math.cos(slat2)
    ) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5)
        / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )

    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (
        math.pow(sf, sn)
        * math.cos(slat1)
        / sn
    )

    ro = math.tan(
        math.pi * 0.25 + olat * 0.5
    )
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(
        math.pi * 0.25 + latitude * degrad * 0.5
    )
    ra = re * sf / math.pow(ra, sn)

    theta = longitude * degrad - olon

    if theta > math.pi:
        theta -= 2.0 * math.pi

    if theta < -math.pi:
        theta += 2.0 * math.pi

    theta *= sn

    nx = int(ra * math.sin(theta) + xo + 0.5)
    ny = int(ro - ra * math.cos(theta) + yo + 0.5)

    return nx, ny

def get_current_weather(nx, ny):
    """
    기상청 초단기실황 API에서 현재 기상정보를 조회한다.

    nx, ny: 기상청 격자 좌표
    """

    if not SERVICE_KEY:
        raise ValueError(
            ".env 파일에서 KMA_SERVICE_KEY를 찾을 수 없습니다."
        )

    base_date, base_time = get_base_datetime()

    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 100,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    result_code = data["response"]["header"]["resultCode"]

    if result_code != "00":
        result_message = data["response"]["header"]["resultMsg"]
        raise RuntimeError(
            f"기상청 API 오류: {result_code} / {result_message}"
        )

    items = data["response"]["body"]["items"]["item"]

    weather = {}

    for item in items:
        category = item["category"]
        value = item["obsrValue"]

        weather[category] = value

    return {
        "temperature": weather.get("T1H"),
        "humidity": weather.get("REH"),
        "rainfall": weather.get("RN1"),
        "wind_speed": weather.get("WSD"),
        "wind_direction": weather.get("VEC"),
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

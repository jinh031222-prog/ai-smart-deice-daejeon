import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENTOPO_KEY")


def get_elevation(latitude: float, longitude: float) -> float:
    """
    OpenTopography Point Elevation API에서
    Copernicus 30m 기반 고도를 조회한다.
    """

    if not API_KEY:
        raise ValueError("OPENTOPO_KEY가 .env에 없습니다.")

    url = "https://portal.opentopography.org/API/point"

    params = {
        "lat": latitude,
        "lon": longitude,
        "demtype": "COP30",
        "outputFormat": "json",
        "API_Key": API_KEY,
    }

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return float(data["results"][0]["elevation"])
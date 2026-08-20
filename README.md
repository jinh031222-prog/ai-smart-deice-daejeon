# AI Smart De-Ice Daejeon

대전광역시 도로 LINK별 블랙아이스 위험도를 분석하고 3D 지도에 시각화하는 Streamlit 대시보드입니다.

## 주요 기능

- 실시간 기상 및 겨울 시뮬레이션 조건 분석
- 도로 경사, 교량·터널, 지형·건물 음영 반영
- 시간대별 건물 음영과 도로 위험도 시각화
- 행정동 검색 및 선택 지역 중심 3D 지도

## 로컬 실행

Python 3.12 환경을 권장합니다.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 배포

대용량 GeoPackage(`.gpkg`)는 Git LFS로 관리합니다. Streamlit Community Cloud에서 저장소를 연결한 뒤 메인 파일을 `app.py`, Python 버전을 `3.12`로 선택합니다.

기상 API 키는 저장소에 올리지 않고 Streamlit의 Secrets 설정에 다음 이름으로 등록합니다.

```toml
KMA_SERVICE_KEY = "발급받은_기상청_API_키"
OPENTOPO_KEY = "발급받은_OpenTopoData_API_키"
```

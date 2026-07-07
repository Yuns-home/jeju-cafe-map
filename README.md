# ☕ 제주 카페 탐방

제주도 카페를 지도·거리검색·분석 대시보드로 살펴보는 Streamlit 앱입니다.
데이터: 소상공인시장진흥공단 상가업소(제주) 중 카페 2,912곳.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 배포 (Streamlit Community Cloud)

1. 이 폴더의 내용을 GitHub 저장소에 push
2. https://share.streamlit.io → **New app**
3. 저장소 선택, Main file path = `app.py` → **Deploy**

## 파일 구성

| 파일 | 설명 |
|------|------|
| `app.py` | Streamlit 앱 본체 |
| `jeju_cafes.parquet` | 경량 데이터 (원본 엑셀에서 카페만 추출, 약 0.2MB) |
| `requirements.txt` | 의존성 (버전 고정) |
| `.streamlit/config.toml` | 테마·서버 설정 |
| `prepare_data.py` | 원본 엑셀 → parquet 재생성 스크립트 |

## 데이터 갱신

원본 `제주상권.xlsx`가 업데이트되면:

```bash
python prepare_data.py 제주상권.xlsx
```

## 참고

- 펫 프렌들리 표시는 원본에 해당 정보가 없어 **상호명 키워드 기반 추정**입니다.

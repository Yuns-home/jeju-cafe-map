# -*- coding: utf-8 -*-
"""
원본 제주상권.xlsx(약 14.5MB)에서 카페 행·필요 컬럼만 추출해
경량 jeju_cafes.parquet(약 0.2MB)로 저장하는 전처리 스크립트.

원본 데이터가 갱신되면 이 스크립트만 다시 실행하면 된다.
    python prepare_data.py [원본엑셀경로]
"""
import sys
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "제주상권.xlsx"
OUT = "jeju_cafes.parquet"

keep = {
    "상호명": "name", "지점명": "branch", "시군구명": "city",
    "행정동명": "dong", "도로명주소": "road_addr", "지번주소": "jibun_addr",
    "건물명": "building", "경도": "lon", "위도": "lat",
}

df = pd.read_excel(SRC, sheet_name="Sheet1")
cafe = df[df["상권업종소분류명"] == "카페"].copy()
cafe = cafe[list(keep)].rename(columns=keep)

# 좌표 유효 범위(제주) 내로 제한
cafe = cafe[cafe["lat"].between(33.0, 34.1) & cafe["lon"].between(126.0, 127.0)].copy()

# 텍스트 컬럼 문자열 통일 (혼합형 방지)
for c in ["name", "branch", "city", "dong", "road_addr", "jibun_addr", "building"]:
    cafe[c] = cafe[c].astype("string")

cafe = cafe.reset_index(drop=True)
cafe.to_parquet(OUT, index=False)
print(f"저장 완료: {OUT} ({len(cafe):,} rows)")

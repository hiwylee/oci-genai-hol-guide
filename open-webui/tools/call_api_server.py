#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["fastapi", "uvicorn[standard]"]
# ///
"""
오라 여행 SSE 스트리밍 API 서버

call_api_sse.py 의 백엔드.
POST /v1/responses/stream  →  SSE 이벤트 스트림

이벤트 포맷:
  data: {"type": "step",   "message": "..."}
  data: {"type": "result", "final": {...}}
  data: [DONE]
"""

import asyncio
import json
import random
import time
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="오라 여행 SSE API", version="1.0.0")

# ── 모의 데이터 ────────────────────────────────────────────────────────────────

PACKAGES = [
    {
        "goods_nm": "오라 여행 | 방콕 5일 자유여행",
        "min_price": 689000,
        "review_avgscore": 4.7,
        "out_air_company_list": "대한항공",
        "goods_image": "https://via.placeholder.com/300x200?text=Bangkok",
        "web_linkurl": "https://example.com/bkk",
    },
    {
        "goods_nm": "오라 여행 | 다낭 4일 리조트",
        "min_price": 549000,
        "review_avgscore": 4.5,
        "out_air_company_list": "티웨이항공",
        "goods_image": "https://via.placeholder.com/300x200?text=Danang",
        "web_linkurl": "https://example.com/dng",
    },
    {
        "goods_nm": "오라 여행 | 도쿄 3박 4일 패키지",
        "min_price": 799000,
        "review_avgscore": 4.6,
        "out_air_company_list": "아시아나항공",
        "goods_image": "https://via.placeholder.com/300x200?text=Tokyo",
        "web_linkurl": "https://example.com/tyo",
    },
    {
        "goods_nm": "오라 여행 | 발리 7일 허니문",
        "min_price": 1290000,
        "review_avgscore": 4.9,
        "out_air_company_list": "가루다인도네시아",
        "goods_image": "https://via.placeholder.com/300x200?text=Bali",
        "web_linkurl": "https://example.com/bali",
    },
]

HOTELS = [
    {
        "hotel_name_ko": "더 스탠다드 방콕",
        "hotel_name_en": "The Standard Bangkok",
        "star_rating": 5.0,
        "country_name_ko": "태국",
        "city_name_ko": "방콕",
        "default_photo_url": "https://via.placeholder.com/300x200?text=Standard+BKK",
        "web_linkurl": "https://example.com/hotel/std-bkk",
        "hotel_intro_ko": "방콕 도심 차오프라야 강변의 세련된 디자인 호텔로, 루프탑 바와 인피니티 풀이 유명합니다.",
    },
    {
        "hotel_name_ko": "인터컨티넨탈 다낭",
        "hotel_name_en": "InterContinental Danang Sun Peninsula",
        "star_rating": 5.0,
        "country_name_ko": "베트남",
        "city_name_ko": "다낭",
        "default_photo_url": "https://via.placeholder.com/300x200?text=IC+Danang",
        "web_linkurl": "https://example.com/hotel/ic-dng",
        "hotel_intro_ko": "썬 페닌슐라 반도에 위치한 럭셔리 리조트로, 프라이빗 비치와 미식 레스토랑을 갖추고 있습니다.",
    },
    {
        "hotel_name_ko": "파크 하얏트 도쿄",
        "hotel_name_en": "Park Hyatt Tokyo",
        "star_rating": 5.0,
        "country_name_ko": "일본",
        "city_name_ko": "도쿄",
        "default_photo_url": "https://via.placeholder.com/300x200?text=ParkHyatt+TYO",
        "web_linkurl": "https://example.com/hotel/ph-tyo",
        "hotel_intro_ko": "신주쿠 고층부에 위치하며 영화 '사랑도 통역이 되나요?' 촬영지로 유명한 아이코닉 호텔입니다.",
    },
    {
        "hotel_name_ko": "포시즌스 리조트 발리",
        "hotel_name_en": "Four Seasons Resort Bali at Sayan",
        "star_rating": 5.0,
        "country_name_ko": "인도네시아",
        "city_name_ko": "발리",
        "default_photo_url": "https://via.placeholder.com/300x200?text=4Seasons+Bali",
        "web_linkurl": "https://example.com/hotel/fs-bali",
        "hotel_intro_ko": "우붓 정글 속 아윤 강 유역에 자리한 세계 최고 수준의 리조트로, 빌라 풀과 스파가 매력입니다.",
    },
]

STEP_MESSAGES = [
    "🔍 여행 키워드 분석 중...",
    "🗺️ 추천 여행지 선별 중...",
    "📦 패키지 상품 검색 중...",
    "🏨 호텔 상품 검색 중...",
    "✨ 결과 정리 중...",
]


# ── SSE 스트림 생성 ────────────────────────────────────────────────────────────

async def sse_stream(query: str) -> AsyncGenerator[str, None]:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    # 1. 단계 이벤트 순차 발행
    for msg in STEP_MESSAGES:
        yield event({"type": "step", "message": msg})
        await asyncio.sleep(0.4)

    # 2. 쿼리 기반 필터링 (모의) — 랜덤 셔플로 다양성 부여
    pkgs = random.sample(PACKAGES, k=min(4, len(PACKAGES)))
    hotels = random.sample(HOTELS, k=min(4, len(HOTELS)))

    final = {
        "기본메시지": (
            f"'{query}' 에 맞는 오라 여행 추천 상품입니다.\n"
            "최저가 보장 · 무이자 할부 · 24시간 여행 도우미 서비스를 제공합니다."
        ),
        "일반 여행지 정보": (
            "### 오라 여행이 선택한 인기 여행지\n"
            "- **태국 방콕** — 활기찬 야시장과 황금 사원의 도시\n"
            "- **베트남 다낭** — 에메랄드빛 바다와 미식의 도시\n"
            "- **일본 도쿄** — 전통과 첨단이 공존하는 메트로폴리스\n"
            "- **인도네시아 발리** — 신들의 섬, 영혼을 충전하는 힐링 여행지"
        ),
        "상품정보": {
            "패키지상품": pkgs,
            "호텔상품": hotels,
        },
    }

    yield event({"type": "result", "final": final})
    yield "data: [DONE]\n\n"


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str


@app.post("/v1/responses/stream")
async def responses_stream(req: QueryRequest):
    return StreamingResponse(
        sse_stream(req.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "OK", "service": "오라 여행 SSE API"}


# ── 엔트리포인트 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

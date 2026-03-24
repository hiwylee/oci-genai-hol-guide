"""
오라 여행 여행상품 SSE 스트리밍 검색 툴

백엔드 SSE 엔드포인트(POST /v1/responses/stream)에 연결하여
파이프라인 진행 상황을 실시간으로 수신하고
완료된 마크다운을 LLM 재출력 없이 직접 UI에 방출합니다.

비교:
  ybtour_search_markdown_table.py  → 백엔드 완료 후 일괄 수신 (non-SSE)
  ybtour_search_sse.py             → 각 단계 이벤트 실시간 수신 (SSE, 이 파일)
"""

import json
import os
import time
from pydantic import BaseModel, Field
import httpx
import dotenv

dotenv.load_dotenv()


class Tools:
    class Valves(BaseModel):
        sse_url: str = os.getenv(
            "SSE_URL", "http://127.0.0.1:8000/v1/responses/stream"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.sse_url = self.valves.sse_url
        self.headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

    async def ybtour_search_sse(
        self,
        query: str = Field(..., description="여행 상품 추천을 위한 사용자 질문"),
        __event_emitter__=None,
    ) -> str:
        """
        오라 여행 여행상품 SSE 스트리밍 검색.
        파이프라인 각 단계 완료 시 상태를 실시간으로 표시하고
        최종 결과를 마크다운으로 직접 UI에 방출합니다.
        """

        async def emit_status(status: str, message: str):
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": status,
                            "description": message,
                            "hidden": False,
                        },
                    }
                )
            else:
                print(f"[{status}] {message}")

        async def emit_message(content: str):
            """마크다운 콘텐츠를 LLM 재출력 없이 직접 UI에 방출"""
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "message", "data": {"content": content}}
                )
            else:
                print(content)

        await emit_status("in_progress", "🔍 상품 검색 시작 (스트리밍)...")
        start_time = time.perf_counter()

        final_data = None

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    self.sse_url,
                    json={"query": query},
                    headers=self.headers,
                ) as response:
                    response.raise_for_status()

                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # "data: " 제거

                        if data_str == "[DONE]":
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")

                        if etype == "step":
                            await emit_status("in_progress", event.get("message", ""))

                        elif etype == "error":
                            step = event.get("step", "?")
                            msg = event.get("message", "알 수 없는 오류")
                            await emit_status("error", f"❌ {step} 오류: {msg}")
                            return f"검색 중 오류가 발생했습니다 ({step}): {msg}"

                        elif etype == "result":
                            final_data = event.get("final", {})

        except httpx.TimeoutException:
            await emit_status("error", "❌ SSE 연결 타임아웃 (60s)")
            return "검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
        except Exception as e:
            await emit_status("error", f"❌ 연결 오류: {type(e).__name__}: {e}")
            return f"검색 중 오류가 발생했습니다: {e}"

        if not final_data:
            await emit_status("complete", "⚠️ 검색 결과 없음")
            return "검색 결과가 없습니다. 여행지나 조건을 바꿔서 다시 시도해 주세요."

        packages = final_data.get("상품정보", {}).get("패키지상품", [])[:4]
        hotels = final_data.get("상품정보", {}).get("호텔상품", [])[:4]

        await emit_status(
            "in_progress",
            f"📦 패키지상품: {len(packages)}개, 호텔상품: {len(hotels)}개",
        )

        if not packages and not hotels:
            await emit_status("complete", "⚠️ 검색 결과 없음")
            return "검색 결과가 없습니다. 여행지나 조건을 바꿔서 다시 시도해 주세요."

        md = []

        # ── HEADER ────────────────────────────────────────────────────────
        md.append("## 🟡 오라 여행 AI 상품검색\n")

        if final_data.get("기본메시지"):
            md.append(f"### ✨ 여행 추천 안내\n{final_data['기본메시지']}\n")

        if final_data.get("일반 여행지 정보"):
            md.append(final_data["일반 여행지 정보"])
            md.append("\n---\n")

        # ── PACKAGES ──────────────────────────────────────────────────────
        if packages:
            md.extend(self._process_packages(packages))

        # ── HOTELS ────────────────────────────────────────────────────────
        if hotels:
            md.extend(self._process_hotels(hotels))

        total_duration = time.perf_counter() - start_time

        # 마크다운을 LLM 재출력 없이 직접 UI에 방출
        await emit_message("\n".join(md))

        await emit_status(
            "complete",
            f"✅ 완료: 패키지 {len(packages)}개, 호텔 {len(hotels)}개 ({total_duration:.1f}s)",
        )

        # LLM 2차 호출용 짧은 신호만 반환 (마크다운 재출력 방지)
        return f"[검색완료: 패키지 {len(packages)}개, 호텔 {len(hotels)}개]"

    def _process_packages(self, packages: list) -> list:
        """패키지 상품 데이터를 마크다운 테이블로 변환"""
        md = []
        md.append("## ✨ 나에게 꼭 맞는 여행 상품을 찾아왔어요!\n")

        prices = [int(p["min_price"]) for p in packages if p.get("min_price")]
        lowest_price = min(prices) if prices else None

        pkg_data = []
        for p in packages:
            price = int(p.get("min_price") or 0)
            rating = float(p.get("review_avgscore") or 0)

            price_text = (
                f"🔥 **{price:,}원~**" if price == lowest_price else f"**{price:,}원~**"
            )

            if rating >= 4.5:
                rating_text = f"🟧 **{rating}**"
            elif rating >= 3.5:
                rating_text = f"🟩 {rating}"
            else:
                rating_text = f"⬜ {rating}"

            pkg_data.append(
                {
                    "image": p.get("goods_image", ""),
                    "name": p.get("goods_nm", ""),
                    "rating": rating_text,
                    "price": price_text,
                    "airline": p.get("out_air_company_list", "-"),
                    "link": p.get("web_linkurl", "#"),
                }
            )

        separator = "|" + "|".join(["---"] * len(pkg_data)) + "|"
        md.append(separator)
        md.append(separator)
        md.append("| " + " | ".join([f'![]({d["image"]})' for d in pkg_data]) + " |")
        md.append("| " + " | ".join([d["name"] for d in pkg_data]) + " |")
        md.append("| " + " | ".join([d["rating"] for d in pkg_data]) + " |")
        md.append("| " + " | ".join([d["price"] for d in pkg_data]) + " |")
        md.append("| " + " | ".join([d["airline"] for d in pkg_data]) + " |")
        md.append(
            "| " + " | ".join([f"[상세보기]({d['link']})" for d in pkg_data]) + " |"
        )
        return md

    def _process_hotels(self, hotels: list) -> list:
        """호텔 상품 데이터를 마크다운 테이블로 변환"""
        md = []
        md.append("\n---\n")
        md.append("## 🏨 TOP 여행지의 추천 호텔은 어떠세요?\n")

        hotel_data = []
        for h in hotels:
            name_ko = h.get("hotel_name_ko", "")
            name_en = h.get("hotel_name_en", "")
            star = float(h.get("star_rating") or 0)
            country = h.get("country_name_ko", "")
            city = h.get("city_name_ko", "")
            image = h.get("default_photo_url", "")
            link = h.get("web_linkurl", "#")
            intro = h.get("hotel_intro_ko", "")

            star_text = "⭐" * int(star)
            if star % 1 >= 0.5:
                star_text += "½"

            location = f"{country} {city}".strip()
            intro_short = intro[:50] + "..." if len(intro) > 50 else intro

            hotel_data.append(
                {
                    "image": image,
                    "name": f"**{name_ko}**<br>{name_en}",
                    "location": location,
                    "star": star_text,
                    "intro": intro_short,
                    "link": link,
                }
            )

        separator = "|" + "|".join(["---"] * len(hotel_data)) + "|"
        md.append(separator)
        md.append(separator)
        md.append(
            "| " + " | ".join([f'![]({d["image"]})' for d in hotel_data]) + " |"
        )
        md.append("| " + " | ".join([d["name"] for d in hotel_data]) + " |")
        md.append("| " + " | ".join([d["location"] for d in hotel_data]) + " |")
        md.append("| " + " | ".join([d["star"] for d in hotel_data]) + " |")
        md.append("| " + " | ".join([d["intro"] for d in hotel_data]) + " |")
        md.append(
            "| "
            + " | ".join(
                [f"[상세보기]({d['link']})" if d["link"] else "-" for d in hotel_data]
            )
            + " |"
        )
        return md


import asyncio


async def main():
    result = await Tools().ybtour_search_sse(
        query="따뜻한 겨울을 보낼 수 있는 여행상품 추천해줘"
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

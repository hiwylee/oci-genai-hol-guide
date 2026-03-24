# Open-WebUI Tools 실습 가이드 — 외부 API를 LLM 도구로 연결하기

> **사전 조건**: Open-WebUI가 `http://<VM_IP>:8080` 에서 정상 동작 중이어야 합니다.

---

## 1. Tools란 무엇인가?

**Tools(도구)** 는 LLM의 텍스트 생성 능력을 **외부 시스템과 연결**하는 Python 플러그인입니다.
LLM이 "이 질문에는 외부 정보가 필요하다"고 판단하면 자동으로 Tool을 호출하고, 결과를 받아 답변을 완성합니다.

```
사용자: "따뜻한 겨울 여행 상품 추천해줘"
    │
    ▼
LLM: "여행 상품 검색이 필요하다 → Tool 호출"
    │
    ▼
[Tool: tour_search_sse]
  → 외부 API 서버에 SSE 요청
  → 진행 상태 실시간 표시
  → 결과 마크다운 직접 출력
    │
    ▼
화면: 패키지·호텔 상품 테이블 표시
```

### Tool vs RAG 비교

| 구분 | RAG (Knowledge Base) | Tools |
|------|---------------------|-------|
| **데이터 원천** | 미리 업로드한 문서 | 실시간 외부 API |
| **적합한 케이스** | 정적 문서 기반 Q&A | 실시간 검색·계산·외부 서비스 호출 |
| **구현 방식** | 벡터 검색 자동 처리 | Python 코드 직접 작성 |
| **데이터 최신성** | 업로드 시점 기준 | 호출 시점 최신 데이터 |

---

## 2. Tool 코드 구조 이해

Open-WebUI Tool은 **단일 Python 파일** 하나로 구성됩니다.

### 필수 구조

```python
"""
title: 도구 이름            ← Open-WebUI 화면에 표시될 이름
author: 작성자
description: 도구 설명
version: 0.1.0
requirements: httpx, pydantic  ← 추가 패키지 (자동 설치)
"""

from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):          # ← 관리자 설정 값 (UI에서 편집 가능)
        api_url: str = "http://..."

    def __init__(self):
        self.valves = self.Valves()

    async def tool_method(           # ← LLM이 호출할 함수
        self,
        query: str = Field(..., description="질문"),  # ← 타입 힌트 필수
        __event_emitter__=None,      # ← 실시간 UI 이벤트 발행용 (선택)
    ) -> str:
        """LLM에게 보여주는 함수 설명 (영어 권장)"""
        ...
        return "결과 문자열"
```

### 핵심 구성 요소

#### Valves — 관리자 설정 값

```python
class Valves(BaseModel):
    sse_url: str = os.getenv("SSE_URL", "http://127.0.0.1:8000/v1/responses/stream")
```

- 코드 수정 없이 **UI에서 값을 변경**할 수 있는 설정 항목
- Tool 등록 후 편집 아이콘 → Valves 항목 수정 가능
- 환경 변수 또는 기본값으로 초기화

#### `__event_emitter__` — 실시간 상태 표시

```python
# 진행 상태 표시 (스피너 + 텍스트)
await __event_emitter__({
    "type": "status",
    "data": {
        "status": "in_progress",   # "in_progress" | "complete" | "error"
        "description": "🔍 검색 중...",
        "hidden": False,
    }
})

# 마크다운 직접 출력 (LLM 재처리 없이 그대로 표시)
await __event_emitter__({
    "type": "message",
    "data": {"content": "## 결과\n| 상품 | 가격 |\n..."}
})
```

> **중요**: `type: "message"` 이벤트는 **Default Mode**에서만 작동합니다.
> Native(Agentic) Mode에서는 LLM 응답으로 덮어써집니다.

#### 반환값 규칙

```python
# message 이벤트로 이미 출력했으면 → 짧은 신호만 반환 (중복 방지)
return "[검색완료: 패키지 3개]"

# 단순 정보 조회 → 결과 문자열 반환 (LLM이 요약해서 출력)
return "현재 기온: 25°C, 맑음"
```

---

## 3. 실습 파일 구조

이 실습에서 사용하는 파일은 두 개입니다.

```
template/openwebui/tools/
├── call_api_sse.py       ← Open-WebUI에 등록할 Tool (클라이언트)
└── call_api_server.py    ← Tool이 호출할 백엔드 SSE API 서버
```

### 역할 분리

```
Open-WebUI (Tool 실행)              백엔드 서버
┌─────────────────────┐             ┌──────────────────────────┐
│  call_api_sse.py    │  POST SSE   │  call_api_server.py      │
│                     │ ──────────► │  FastAPI                 │
│  Tools 클래스        │             │  POST /v1/responses/stream│
│  tour_search_sse()│ ◄────────── │                          │
│  → 상태 이벤트 방출   │  이벤트 스트림 │  step 이벤트 → 진행상황  │
│  → 마크다운 직접 출력 │             │  result 이벤트 → 최종결과 │
└─────────────────────┘             └──────────────────────────┘
```

### call_api_sse.py 핵심 로직

```python
# 1. SSE 스트리밍 연결
async with client.stream("POST", self.sse_url, json={"query": query}) as response:
    async for raw_line in response.aiter_lines():
        # SSE 포맷: "data: {json}\n\n"
        data_str = line[6:]            # "data: " 제거
        event = json.loads(data_str)

        if event["type"] == "step":
            # 단계별 진행 상태 표시
            await emit_status("in_progress", event["message"])

        elif event["type"] == "result":
            # 최종 결과 데이터 수신
            final_data = event["final"]

# 2. 결과를 마크다운으로 변환 후 직접 UI에 방출
await emit_message("\n".join(markdown_lines))

# 3. LLM에는 짧은 신호만 반환 (마크다운 재출력 방지)
return "[검색완료: 패키지 3개, 호텔 3개]"
```

---

## 4. 백엔드 서버 실행

Tool이 호출할 백엔드 API 서버를 먼저 VM에서 실행합니다.

### Step 1 — 패키지 설치

```bash
pip install fastapi uvicorn httpx
# 또는 uv 사용
uv pip install fastapi uvicorn httpx
```

### Step 2 — 서버 실행

```bash
python ~/hol/templates/openwebui/tools/call_api_server.py
```

실행 성공 시 출력:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Step 3 — 서버 동작 확인

```bash
# 헬스체크
curl http://localhost:8000/health
# 예상: {"status":"OK","service":"오라 여행 SSE API"}

# SSE 스트리밍 테스트
curl -N -X POST http://localhost:8000/v1/responses/stream \
     -H "Content-Type: application/json" \
     -d '{"query": "따뜻한 겨울 여행"}'
```

SSE 테스트 예상 출력:
```
data: {"type": "step", "message": "🔍 여행 키워드 분석 중..."}
data: {"type": "step", "message": "🗺️ 추천 여행지 선별 중..."}
data: {"type": "step", "message": "📦 패키지 상품 검색 중..."}
data: {"type": "step", "message": "🏨 호텔 상품 검색 중..."}
data: {"type": "step", "message": "✨ 결과 정리 중..."}
data: {"type": "result", "final": {...}}
data: [DONE]
```

### Step 4 — 백그라운드 실행 (선택)

SSH 세션 종료 후에도 서버를 유지하려면:

```bash
nohup python ~/hol/templates/openwebui/tools/call_api_server.py \
      > ~/hol/api_server.log 2>&1 &

echo "PID: $!"   # 나중에 종료할 때 사용

# 로그 확인
tail -f ~/hol/api_server.log
```

---

## 5. Open-WebUI에 Tool 등록

### Step 1 — Tool 코드 복사

VM에서 `call_api_sse.py` 내용을 복사합니다:

```bash
cat ~/hol/templates/openwebui/tools/call_api_sse.py
```

전체 내용을 클립보드에 복사합니다.

### Step 2 — Workspace > Tools 접속

브라우저에서 `http://<VM_IP>:8080` 접속 후:

1. 왼쪽 사이드바 하단 **사용자 아이콘** 클릭 → **Workspace**
2. 상단 탭 **Tools** 클릭
3. 오른쪽 상단 **+ (새 Tool 추가)** 버튼 클릭

### Step 3 — 코드 붙여넣기

에디터 화면이 열리면:

1. 기존 코드를 모두 선택 (`Ctrl+A`)하고 삭제
2. 복사해둔 `call_api_sse.py` 내용 붙여넣기 (`Ctrl+V`)

화면 상단에서 자동으로 파싱된 메타데이터 확인:
- **Name**: `오라 여행 여행상품 SSE 스트리밍 검색 툴`
- **Description**: 파일 최상단 독스트링 내용

### Step 4 — Valves 설정 확인

오른쪽 패널 또는 저장 후 편집 아이콘 → **Valves** 항목:

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `sse_url` | `http://127.0.0.1:8000/v1/responses/stream` | 백엔드 SSE 서버 URL |

> **컨테이너 환경 주의**: Open-WebUI는 컨테이너 안에서 실행됩니다.
> `127.0.0.1`은 Open-WebUI 컨테이너 자신을 가리키므로, VM 호스트에서 실행 중인 백엔드 서버에 접근하려면 VM의 실제 IP 또는 컨테이너 게이트웨이 IP를 사용해야 합니다.
>
> ```bash
> # VM 호스트 IP 확인 (컨테이너에서 호스트로 접근할 IP)
> ip route | grep default | awk '{print $3}'
> # 예: 10.88.0.1
> ```
>
> Valves의 `sse_url`을 `http://10.88.0.1:8000/v1/responses/stream` 으로 변경합니다.

### Step 5 — 저장

**Save** 버튼 클릭

Tools 목록에 새 항목이 추가되면 등록 완료입니다.

---

## 6. 채팅에서 Tool 사용

### 방법 A — 채팅 세션에서 즉석 활성화

1. **New Chat** 클릭
2. 모델 선택 (예: `meta.llama-3.3-70b-instruct`)
3. 입력창 왼쪽 **+ (도구)** 버튼 클릭
4. `오라 여행 여행상품 SSE 스트리밍 검색 툴` 토글 활성화
5. 질문 입력:

```
따뜻한 겨울을 보낼 수 있는 여행 상품 추천해줘
```

### 방법 B — 모델에 기본 Tool로 설정

매번 활성화하지 않으려면:

1. **Workspace > Models** → 사용 모델 편집 아이콘
2. **Tools** 섹션 → `오라 여행 여행상품 SSE 스트리밍 검색 툴` 체크
3. **Save**

이후 해당 모델로 채팅 시 Tool이 자동으로 활성화됩니다.

### 예상 동작 흐름

```
[사용자 질문]
"발리 여행 패키지 추천해줘"

[LLM 판단]
여행 상품 검색이 필요 → tour_search_sse 호출

[Tool 실행 중 화면]
◐ 🔍 상품 검색 시작 (스트리밍)...
◐ 🔍 여행 키워드 분석 중...
◐ 🗺️ 추천 여행지 선별 중...
◐ 📦 패키지 상품 검색 중...
◐ 🏨 호텔 상품 검색 중...
◐ ✨ 결과 정리 중...
◐ 📦 패키지상품: 4개, 호텔상품: 4개

[결과 출력]
## 🔵 오라 여행 AI 상품검색

### ✨ 여행 추천 안내
'발리 여행 패키지 추천해줘'에 맞는 오라 여행 추천 상품입니다.

| --- | --- | --- | --- |
| [이미지] | [이미지] | ... |
| 발리 7일 허니문 | 방콕 5일 자유여행 | ... |
...

✅ 완료: 패키지 4개, 호텔 4개 (2.1s)
```

---

## 7. Tool 개발 모드 선택

Open-WebUI Tool은 두 가지 동작 모드를 가집니다. 작성한 Tool의 특성에 맞게 선택합니다.

### Default Mode (기본값)

```
LLM → Tool 호출 → 결과 반환 → LLM이 결과를 다시 텍스트로 출력
```

- `type: "message"` 이벤트로 **마크다운 직접 출력** 가능
- 진행 상태 스피너 표시 가능
- **이 실습 파일(`call_api_sse.py`)이 사용하는 모드**

### Native Mode (Agentic Mode)

```
LLM → Tool 호출 → 결과 반환 → LLM이 직접 판단하여 추가 Tool 호출 가능
```

- 여러 Tool을 연속으로 자동 호출하는 **자율 실행(agentic)** 가능
- `type: "message"` 이벤트 미지원 (LLM 출력으로 덮어씌워짐)
- 고품질 모델 필요

#### Native Mode 활성화 방법

채팅 창 오른쪽 설정 아이콘 → **Advanced Params** → **Function Calling** → `Native` 선택

---

## 8. 문제 해결

### Tool이 호출되지 않는 경우

```
확인 1: 채팅창의 + 버튼에서 해당 Tool이 활성화되어 있는지 확인
확인 2: 사용 모델이 Function Calling을 지원하는지 확인
        (meta.llama-3.3-70b-instruct 권장)
```

### SSE 연결 오류 — "연결 오류: ConnectError"

```bash
# 백엔드 서버가 실행 중인지 확인
curl http://localhost:8000/health

# 컨테이너에서 호스트 IP로 접근 테스트
GATEWAY_IP=$(ip route | grep default | awk '{print $3}')
echo "컨테이너 게이트웨이 IP: ${GATEWAY_IP}"
curl http://${GATEWAY_IP}:8000/health
```

Open-WebUI Valves에서 `sse_url`을 컨테이너 게이트웨이 IP로 수정:
```
http://10.88.0.1:8000/v1/responses/stream  ← 실제 IP로 변경
```

### Tool 저장 시 문법 오류

```
확인: Python 들여쓰기가 공백 4칸으로 일관되는지 확인
확인: 클래스 메서드에 타입 힌트가 있는지 확인
     (없으면 LLM이 파라미터를 인식하지 못함)
```

### 마크다운 결과가 출력되지 않고 LLM 텍스트만 나오는 경우

```
원인: Native Mode가 활성화되어 있음
해결: 채팅 설정 → Function Calling → "Default" 로 변경
```

---

## 9. 나만의 Tool 만들기 — 코드 템플릿

이 실습 파일을 기반으로 다른 API를 연결하는 Tool을 만들어 보세요.

```python
"""
title: 나의 커스텀 Tool
author: 내 이름
description: 무엇을 하는 Tool인지 설명
version: 0.1.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        api_url: str = "http://your-api-server:PORT/endpoint"

    def __init__(self):
        self.valves = self.Valves()

    async def my_tool_function(
        self,
        query: str = Field(..., description="LLM에게 보여줄 파라미터 설명"),
        __event_emitter__=None,
    ) -> str:
        """
        LLM이 이 함수를 언제 호출할지 판단하는 데 사용하는 설명.
        영어로 작성하면 더 잘 인식됩니다.
        """
        # 진행 상태 표시
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"status": "in_progress", "description": "처리 중..."}
            })

        # 외부 API 호출
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.valves.api_url,
                json={"query": query}
            )
            result = resp.json()

        # 완료 상태 표시
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"status": "complete", "description": "완료"}
            })

        return str(result)
```

---

## 참고 자료

| 자료 | 링크 |
|------|------|
| Open WebUI Tools 공식 문서 | https://docs.openwebui.com/features/extensibility/plugin/tools/ |
| Tool 개발 가이드 | https://docs.openwebui.com/features/extensibility/plugin/tools/development |
| 커뮤니티 Tool 라이브러리 | https://openwebui.com/tools |
| SSE(Server-Sent Events) 개요 | https://developer.mozilla.org/ko/docs/Web/API/Server-sent_events |

---

**← 이전**: [03_rag_guide.md](./03_rag_guide.md)
**↑ 메인**: [00_README.md](./00_README.md)

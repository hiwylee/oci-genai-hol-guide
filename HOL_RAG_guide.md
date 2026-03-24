# RAG 실습 가이드 — HOL 문서로 나만의 Knowledge Base 만들기

> **사전 조건**: Open-WebUI가 `http://<VM_IP>:8080` 에서 정상 동작 중이어야 합니다.
> 아직 환경 설정이 완료되지 않았다면 [HOL_step_by_step.md](./HOL_step_by_step.md) 를 먼저 진행하세요.

---

## 1. RAG란 무엇인가?

**RAG (Retrieval-Augmented Generation)** 는 LLM이 외부 문서를 참고해 답변하도록 만드는 기법입니다.

### LLM만 사용할 때의 한계

```
사용자: "우리 HOL 실습에서 사용하는 임베딩 모델 이름이 뭔가요?"
LLM:   "죄송합니다. 학습 데이터에 해당 정보가 없습니다." ← 사내 문서 / HOL 전용 정보는 모름
```

| 문제 | 설명 |
|------|------|
| **지식 한계** | 학습 데이터 이후의 신규 정보를 모름 |
| **비공개 문서** | 사내 문서, 실습 가이드 등 공개되지 않은 내용 미지원 |
| **Hallucination** | 근거 없이 그럴듯한 오답을 생성 |

### RAG를 적용하면

```
사용자: "우리 HOL 실습에서 사용하는 임베딩 모델 이름이 뭔가요?"

[RAG 파이프라인]
  1. 질문 → 벡터 변환
  2. HOL 가이드 문서에서 유사 내용 검색
  3. 검색된 내용 + 질문을 LLM에 전달

LLM: "HOL_prerequisites.md 문서에 따르면, 이 실습에서 사용하는
     임베딩 모델은 cohere.embed-v4.0 (1024차원)입니다." ✓
```

### RAG 처리 흐름

**[문서 저장 단계]**
```
HOL 가이드 파일 업로드
        │
        ▼
청크 분할 (긴 문서 → 작은 조각)
        │
        ▼
임베딩 모델 호출 (cohere.embed-v4.0)
텍스트 → 1024차원 숫자 벡터
        │
        ▼
Oracle ADW AI Vector Search에 저장
```

**[질문 처리 단계]**
```
사용자 질문 입력
        │
        ▼
질문도 벡터로 변환 (cohere.embed-v4.0)
        │
        ▼
Oracle ADW에서 유사 벡터 검색 (코사인 유사도)
        │
        ▼
관련 문서 조각 추출
        │
        ▼
LLM에게 [질문 + 검색된 문서 조각] 함께 전달
        │
        ▼
LLM이 문서 근거로 답변 생성 + 출처 표시
```

---

## 2. 이 실습에서 만드는 것

HOL 가이드 문서 3개를 Knowledge Base로 등록하고, 이를 참조하는 맞춤형 모델을 만든 뒤 실제 HOL 관련 질문을 해봅니다.

```
HOL_Guide/
├── HOL_README.md          ← 실습 개요, 아키텍처
├── HOL_prerequisites.md   ← 개념 설명, 사전 준비
└── HOL_step_by_step.md    ← 단계별 실습 명령어
        │
        ▼ (업로드)
  [Knowledge Base: "OCI GenAI HOL 가이드"]
        │
        ▼ (연결)
  [모델: "HOL 도우미"]
        │
        ▼ (질문)
  "Gateway config 파일이 왜 두 개인가요?"
        │
        ▼ (RAG 검색 → 답변)
  HOL_prerequisites.md 내용을 근거로 답변
```

---

## 3. Knowledge Base 생성

### Step 1 — Workspace 메뉴 접근

브라우저에서 `http://<VM_IP>:8080` 접속 후:

1. 왼쪽 사이드바 하단 **사용자 아이콘** 클릭 → **Workspace** 선택
2. 상단 탭에서 **Knowledge** 클릭
3. 오른쪽 상단 **+ (Create a Knowledge Base)** 버튼 클릭

### Step 2 — Knowledge Base 정보 입력

| 필드 | 입력값 |
|------|--------|
| **Name** | `OCI GenAI HOL 가이드` |
| **Description** | `OCI GenAI HOL 실습 가이드 문서 모음` |
| **Visibility** | `Private` |

**Create Knowledge** 버튼 클릭

### Step 3 — 문서 파일 준비

HOL 가이드 파일은 실습 VM의 `/home/opc/projects/oci_genai_hol/HOL_Guide/` 디렉터리에 있습니다.
로컬 PC로 다운로드하거나, 아래 방법으로 직접 접근합니다.

**VM에서 파일 내용 확인** (각 파일을 하나씩 복사해 로컬에 저장):
```bash
# 파일 목록 확인
ls ~/hol/templates/HOL_Guide/

# 또는 실습 파일 위치 확인
ls /home/opc/projects/oci_genai_hol/HOL_Guide/
```

> **MobaXterm 사용자**: 왼쪽 파일 브라우저에서 해당 경로로 이동 후
> `HOL_README.md`, `HOL_prerequisites.md`, `HOL_step_by_step.md` 파일을 드래그하여 로컬 PC로 저장

> **Mac/Linux 사용자**: `scp` 명령으로 파일 다운로드:
> ```bash
> scp -i ssh-hol.key opc@<VM_IP>:/home/opc/projects/oci_genai_hol/HOL_Guide/HOL_*.md ~/Downloads/
> ```

### Step 4 — 파일 업로드

Knowledge Base 화면에서:

1. 화면 중앙 **파일 업로드 영역**으로 아래 파일을 드래그 앤 드롭:
   - `HOL_README.md`
   - `HOL_prerequisites.md`
   - `HOL_step_by_step.md`

2. 업로드 완료 후 파일 목록에 3개 파일이 표시되는지 확인

> 업로드 시 Open-WebUI가 자동으로 다음 작업을 수행합니다:
> - 문서를 청크(조각)로 분할
> - `cohere.embed-v4.0` 모델로 각 청크를 벡터로 변환
> - Oracle ADW AI Vector Search에 저장

---

## 4. RAG 전용 모델 생성

### Step 1 — 모델 추가 메뉴 접근

1. **Workspace** → **Models** 탭 클릭
2. 오른쪽 상단 **+ (Add New Model)** 버튼 클릭

### Step 2 — 모델 설정

| 필드 | 입력값 | 설명 |
|------|--------|------|
| **Name** | `HOL 도우미` | 채팅창 모델 목록에 표시될 이름 |
| **Base Model** | `meta.llama-3.3-70b-instruct` | 또는 원하는 OCI GenAI 모델 선택 |
| **Description** | `OCI GenAI HOL 가이드 문서 기반 Q&A 모델` | |
| **System Prompt** | 아래 참조 | |

**System Prompt 예시**:
```
당신은 OCI GenAI HOL(Hands-on Lab) 실습 도우미입니다.
제공된 HOL 가이드 문서를 참고하여 수강생의 질문에 한국어로 답변합니다.
문서에 없는 내용은 "가이드 문서에 해당 내용이 없습니다"라고 안내하세요.
답변 시 관련 문서 파일명과 섹션을 함께 알려주세요.
```

### Step 3 — Knowledge Base 연결

모델 설정 화면에서:

1. **Knowledge** 항목을 찾아 드롭다운 클릭
2. `OCI GenAI HOL 가이드` 선택

### Step 4 — 저장

**Save** 버튼 클릭

---

## 5. RAG 실습 — 질문해보기

### 기본 RAG 채팅

1. 왼쪽 사이드바 **New Chat** (또는 `Ctrl+Shift+O`) 클릭
2. 상단 모델 선택 드롭다운에서 **"HOL 도우미"** 선택
3. 아래 예제 질문을 입력하고 답변을 확인합니다

---

### 예제 질문 모음

#### [개념 이해] 아키텍처 관련

**질문 1**
```
이 HOL 실습에서 만드는 시스템의 전체 아키텍처를 설명해 주세요.
어떤 컴포넌트들이 어떻게 연결되나요?
```
> 기대 답변: HOL_README.md의 아키텍처 다이어그램 내용 — Open-WebUI, Gateway, ADW, OCI GenAI 연결 구조

---

**질문 2**
```
왜 OCI CLI용 config 파일과 Gateway용 config 파일이 따로 필요한가요?
둘의 차이점은 무엇인가요?
```
> 기대 답변: HOL_prerequisites.md §4 내용 — 리전 차이(춘천 vs 시카고), 목적 차이(IAM·ADW vs GenAI API 호출)

---

**질문 3**
```
hol-net이란 무엇이고, Open-WebUI가 Gateway에 접근할 때
localhost:8088 대신 컨테이너명을 사용하는 이유가 뭔가요?
```
> 기대 답변: HOL_prerequisites.md §8 내용 — Podman 브릿지 네트워크, 컨테이너 내부 localhost 개념

---

#### [실습 절차] 명령어 관련

**질문 4**
```
setup.sh를 실행하면 어떤 단계들이 자동으로 실행되나요?
각 단계의 역할을 간략히 설명해 주세요.
```
> 기대 답변: HOL_README.md §1단계 — 11개 단계 목록 및 설명

---

**질문 5**
```
Gateway 컨테이너를 실행하는 podman run 명령어에서
-v 옵션으로 .oci 디렉터리를 마운트하는 이유가 무엇인가요?
그리고 key_file 경로가 /root/.oci/ 인 이유는?
```
> 기대 답변: HOL_step_by_step.md Step 10 및 Step 3 내용 — 인증 파일 마운트, 컨테이너 내부 경로

---

**질문 6**
```
ADW Wallet 파일 중에서 envsubst로 처리하면 안 되는 파일은 무엇이고,
그 이유는 무엇인가요?
```
> 기대 답변: HOL_step_by_step.md Step 4 내용 — 바이너리 파일(cwallet.sso, ewallet.p12) vs 텍스트 파일

---

#### [RAG / 임베딩] 기술 관련

**질문 7**
```
이 HOL에서 RAG를 위해 사용하는 임베딩 모델은 무엇이고,
벡터 차원 수는 얼마인가요? 그 벡터는 어디에 저장되나요?
```
> 기대 답변: HOL_step_by_step.md Step 8 내용 — cohere.embed-v4.0, 1024차원, Oracle ADW AI Vector Search

---

**질문 8**
```
Open-WebUI .env 파일에서 RAG_EMBEDDING_ENGINE과
RAG_EMBEDDING_MODEL 항목은 각각 무엇을 의미하나요?
```
> 기대 답변: HOL_step_by_step.md Step 8 내용 — .env 주요 항목 설명

---

#### [문제 해결] 트러블슈팅 관련

**질문 9**
```
Gateway에서 OCI API 호출 시 NotAuthenticated 오류가 발생합니다.
무엇을 확인해야 하나요?
```
> 기대 답변: HOL_prerequisites.md §4 오류 1 내용 — fingerprint, key_file 경로 불일치 확인 방법

---

**질문 10**
```
SSH 재접속 후 컨테이너가 사라졌습니다. 왜 이런 일이 발생하고
어떻게 해결하나요?
```
> 기대 답변: HOL_README.md 문제해결 섹션 — loginctl enable-linger 설정 확인 및 podman start 명령

---

### Knowledge Base 직접 참조 (@파일명)

특정 파일을 콕 집어서 참조할 수도 있습니다:

```
@HOL_prerequisites  OCI API Key 인증 방식의 동작 원리를 RSA 키 교환 관점에서 설명해 주세요.
```

```
@HOL_step_by_step  Open-WebUI 컨테이너 실행 시 --restart=always 옵션이 없으면 어떻게 되나요?
```

---

## 6. RAG 품질 확인 — 출처 검증

Open-WebUI는 RAG 답변 시 **참조한 문서 조각(Source)** 을 함께 표시합니다.

답변 하단에서 확인할 사항:
- 어떤 파일에서 가져왔는지 (`HOL_README.md` 등)
- 몇 번째 청크인지 (chunk index)
- 유사도 점수 (relevance score)

> 출처가 표시되지 않거나 엉뚱한 내용을 참조한다면 아래 **RAG 설정 조정** 섹션을 참조하세요.

---

## 7. RAG 설정 조정 (관리자)

RAG 검색 품질이 낮을 경우 **Admin Panel > Settings > Documents** 에서 조정합니다.

### 주요 파라미터

| 항목 | 기본값 | 설명 |
|------|--------|------|
| **Chunk Size** | 1500 | 문서를 나누는 조각 크기(토큰 수). 작을수록 정밀, 클수록 맥락 유지 |
| **Chunk Overlap** | 100 | 인접 청크 간 겹치는 토큰 수. 문장 경계 단절 방지 |
| **Top K** | 5 | 검색 시 반환할 최대 청크 수 |
| **Minimum Score** | 0.0 | 유사도 점수 하한선. 높을수록 엄격 |

### HOL 가이드 파일에 권장하는 설정

```
Chunk Size:    1000   (마크다운 섹션 단위로 분할)
Chunk Overlap: 200    (### 헤더 경계를 넘어 맥락 유지)
Top K:         5      (관련 섹션 5개 참조)
```

변경 후 Knowledge Base에서 파일을 **재처리(Reprocess)** 해야 적용됩니다:
Knowledge → 파일 선택 → **Reprocess** 버튼 클릭

---

## 8. 심화: Knowledge Base 없이 파일 직접 첨부

매번 Knowledge Base를 설정하지 않고, 채팅창에서 즉석으로 파일을 참조할 수도 있습니다.

1. 채팅창 **+ (첨부)** 버튼 클릭
2. 마크다운 파일 선택 및 업로드
3. 질문 입력

```
(HOL_step_by_step.md 첨부 후)
"이 문서에서 podman build 명령어는 몇 단계에서 실행하나요?"
```

> 파일 첨부 방식은 해당 채팅 세션에서만 유효합니다.
> 반복적으로 사용하려면 Knowledge Base 등록을 권장합니다.

---

## 9. 정리 — RAG 아키텍처 전체 흐름 (이 HOL 기준)

```
[브라우저]
사용자가 "HOL 도우미" 모델에 질문
    │
    ▼
[Open-WebUI :8080]
  1. 질문 텍스트 수신
  2. cohere.embed-v4.0으로 질문 벡터화
     └─ Gateway → OCI GenAI (us-chicago-1) 호출
  3. Oracle ADW에서 Top-K 유사 청크 검색
     └─ AI Vector Search (코사인 유사도)
  4. [System Prompt + 검색된 청크 + 사용자 질문] 조합
    │
    ▼
[Gateway :8088]
  OpenAI 형식 → OCI GenAI SDK 변환
    │
    ▼
[OCI Generative AI (us-chicago-1)]
  meta.llama-3.3-70b-instruct 추론
    │
    ▼
[Open-WebUI]
  답변 + 참조 출처 표시
    │
    ▼
[브라우저]
  사용자에게 답변 + 근거 문서 표시
```

---

## 참고 자료

| 자료 | 링크 |
|------|------|
| Open WebUI RAG 공식 튜토리얼 | https://docs.openwebui.com/tutorials/tips/rag-tutorial/ |
| Open WebUI Knowledge 문서 | https://docs.openwebui.com/features/workspace/knowledge |
| Oracle ADW AI Vector Search | https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/ |
| OCI GenAI Embedding 모델 | https://docs.oracle.com/en-us/iaas/Content/generative-ai/embed-models.htm |

---

**← 이전**: [HOL_step_by_step.md](./HOL_step_by_step.md)
**↑ 메인**: [HOL_README.md](./HOL_README.md)

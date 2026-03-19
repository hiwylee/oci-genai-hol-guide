# OCI GenAI Hands-on Lab

## 실습 개요

이 HOL에서는 **OCI Generative AI** 서비스를 활용한 **RAG 챗봇 플랫폼**을 직접 구축합니다.

- 단순한 API 호출 실습이 아니라, **실제 서비스에 가까운 구성**을 컨테이너로 배포합니다.
- 실습 완료 후 브라우저에서 LLM과 채팅하고, 직접 올린 문서를 기반으로 답변을 받을 수 있습니다.

---

## 실습하면 뭘 만들게 되나요?

```
내 PC 브라우저  →  Open-WebUI (채팅 UI)  →  OCI GenAI Gateway  →  OCI GenAI (LLM/Embedding)
                         |
                   Oracle ADW (DB)
                   · 채팅 기록, 사용자 관리
                   · 문서 벡터 저장 (RAG)
```

브라우저에서 채팅 UI(`http://<내 VM IP>:8080`)에 접속해, 34개 이상의 OCI GenAI 모델 중 하나를 골라 대화하고, 업로드한 문서를 기반으로 RAG 검색 답변을 확인합니다.

---

## 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────────────────┐
│  참가자 PC 브라우저                                                        │
│  http://<인스턴스_IP>:8080                                                │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTP
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  OCI Compute Instance (Oracle Linux 9 · 내 VM)                           │
│                                                                          │
│  ┌─────────────────────┐  hol-net   ┌──────────────────────────────────┐ │
│  │  open-webui         │◄──────────►│  oci-genai-access-gateway        │ │
│  │  :8080              │  컨테이너    │  :8088                           │ │
│  │                     │  DNS 통신  │                                  │ │
│  │  · 채팅 인터페이스      │            │  · OpenAI API 호환 레이어       │ │
│  │  · RAG 파이프라인      │            │  · OCI GenAI SDK 호출           │ │
│  │  · 문서 업로드·검색.    │            │  · API Key: ocigenerativeai     │ │
│  └──────────┬──────────┘            └──────────────┬───────────────────┘ │
│             │ Oracle DB (Wallet TLS)               │ HTTPS               │
└─────────────┼─────────────────────────────────────┼─────────────────────┘
              │                                      │
              ▼                                      ▼
┌─────────────────────────┐         ┌────────────────────────────────────┐
│  Oracle ADW             │         │  OCI Generative AI                 │
│  (ap-chuncheon-1)       │         │  (us-chicago-1)                    │
│                         │         │                                    │
│  · 메타데이터 DB           │         │  · LLM: meta.llama, cohere 등      │
│    사용자·채팅·모델         │         │  · Embedding: cohere.embed-v4.0   │
│  · 벡터 저장소 (RAG)       │         │  · 34개+ 모델 지원                    │
└─────────────────────────┘         └────────────────────────────────────┘
```

---

## 구성 요소 한눈에 보기

| 구성 요소 | 역할 | 실행 위치 |
|-----------|------|-----------|
| **Open-WebUI** | 채팅 UI, 파일 업로드, RAG, 모델 관리 | 내 VM (Podman 컨테이너) |
| **OCI GenAI Access Gateway** | OCI GenAI API를 OpenAI 호환 형식으로 변환하는 프록시 | 내 VM (Podman 컨테이너) |
| **Oracle ADW** | 채팅 기록·사용자 저장(메타데이터) + 문서 벡터 저장(RAG) | OCI (춘천 리전) |
| **OCI Generative AI** | LLM 추론 · 임베딩 API | OCI (시카고 리전) |
| **Podman hol-net** | 두 컨테이너가 이름으로 서로 통신하는 내부 네트워크 | 내 VM |

### 리전이 두 개인 이유

| 리전 | 식별자 | 용도 |
|------|--------|------|
| 한국 춘천 | `ap-chuncheon-1` | OCI CLI, IAM 인증, ADW |
| 미국 시카고 | `us-chicago-1` | OCI Generative AI 서비스 |

> OCI GenAI는 특정 리전에서만 제공됩니다.
> Gateway가 시카고 리전 GenAI API를 호출하고, OCI CLI와 ADW는 홈리전(춘천)을 사용합니다.

---

## 실습 진행 순서

### 1단계 — 환경 자동 설정 (약 10분)

SSH로 내 VM에 접속한 뒤, 명령 한 줄로 전체 환경을 구성합니다.

```bash
cd ~/hol && ./setup.sh
```

자동으로 실행되는 11개 단계:

| # | 내용 | 비고 |
|---|------|------|
| 1 | 환경 변수 로드 (`variables.sh`) | 강사가 미리 설정 |
| 2 | Python 패키지 관리자 `uv` 설치 | 이미 있으면 건너뜀 |
| 3 | OCI CLI 인증 설정 (`~/.oci/config`) | |
| 4 | ADW Wallet 파일 준비 | 바이너리는 미리 배포됨 |
| 5 | Gateway 소스 GitHub clone | |
| 6 | Gateway `config.py` 생성 | GenAI 리전 설정 포함 |
| 7 | Gateway 컨테이너용 OCI 인증 파일 복사 | |
| 8 | Open-WebUI `.env` 생성 | DB·Gateway 연결 정보 |
| 9 | 방화벽 포트 오픈 + 컨테이너 지속성 설정 | |
| 10 | Gateway 이미지 빌드 + 컨테이너 실행 | 이미지 빌드 3~5분 |
| 11 | Open-WebUI 이미지 pull + 컨테이너 실행 | |

### 2단계 — 브라우저 접속

설정 완료 후 화면에 출력되는 URL로 접속합니다.

```
Open-WebUI : http://<내 VM 공인 IP>:8080
Gateway    : http://<내 VM 공인 IP>:8088/health
```

### 3단계 — Open-WebUI 초기 설정

1. `http://<IP>:8080` 접속
2. **첫 접속 시 관리자 계정 생성** (이름, 이메일, 비밀번호 입력)
3. **Settings → Connections** 에서 OpenAI API 연결 확인
   - URL: `http://oci-genai-access-gateway:8088/v1` (자동 설정됨)
   - Key: `ocigenerativeai` (자동 설정됨)
4. 상단 모델 선택 → OCI GenAI 모델 선택 → 채팅 시작

### 4단계 — RAG 실습

1. **Documents** 메뉴 → PDF, TXT, DOCX 등 파일 업로드
2. 채팅창에서 `#문서명` 입력 후 질문
3. 문서 내용을 기반으로 한 답변 확인

> 임베딩 모델: `cohere.embed-v4.0` (us-chicago-1, 1536차원)

---

## 서비스 상태 확인

```bash
# 실행 중인 컨테이너 목록
podman ps

# Gateway 헬스체크
curl http://localhost:8088/health
# 예상 결과: {"status":"OK"}

# 사용 가능한 모델 목록 조회
curl -s http://localhost:8088/v1/models \
     -H "Authorization: Bearer ocigenerativeai" | jq '.data[].id'

# Gateway 로그
podman logs oci-genai-access-gateway --tail 30

# Open-WebUI 로그
podman logs open-webui --tail 30
```

---

## 문제 해결

### 컨테이너가 시작되지 않는 경우

```bash
# 상태 확인
podman ps -a

# 처음부터 재실행
podman rm -f open-webui oci-genai-access-gateway 2>/dev/null
podman volume rm open-webui 2>/dev/null
cd ~/hol && ./setup.sh
```

### Gateway API 인증 오류

```bash
# OCI config 확인
cat ~/hol/oci_genai_gateway/.oci/config
# key_file=/root/.oci/oci_api_key.pem 인지 확인

# 개인키 존재 여부 확인
ls -la ~/hol/oci_genai_gateway/.oci/oci_api_key.pem
```

### Open-WebUI DB 연결 오류

```bash
# Wallet 파일 확인
ls -la ~/hol/wallet/

# 접속 DSN 확인
cat ~/hol/wallet/tnsnames.ora
```

### SSH 재접속 후 컨테이너가 없는 경우

```bash
# Linger 상태 확인
loginctl show-user opc | grep Linger

# Linger 비활성화된 경우 활성화
sudo loginctl enable-linger opc

# 컨테이너 재시작
podman start oci-genai-access-gateway open-webui
```

---

## 선택 설치 (심화 실습용)

> `git`과 `podman`은 VM 생성 시 자동 설치됩니다.
> 아래는 직접 개발·운영이 필요한 경우에만 설치합니다.

```bash
# uv (Python 패키지 관리자)
curl -LsSf https://astral.sh/uv/install.sh | sh

# nvm + Node.js 22
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc && nvm install 22 && nvm use 22

# Java / SQLcl
sudo dnf install jdk-24-headless.x86_64 sqlcl -y

# 추가 포트 오픈 (MCPO 등)
sudo firewall-cmd --permanent --add-port=3000/tcp --add-port=8000/tcp
sudo firewall-cmd --reload
```

---

## 참고 자료

| 자료 | URL |
|------|-----|
| OCI Generative AI 공식 문서 | https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm |
| OCI GenAI Access Gateway | https://github.com/hiwylee/OCI_GenAI_access_gateway |
| Open-WebUI | https://github.com/open-webui/open-webui |
| Oracle ADW 공식 문서 | https://docs.oracle.com/en-us/iaas/autonomous-database/ |
| Podman 공식 문서 | https://docs.podman.io/ |

---

## 단계별 상세 가이드

각 단계의 스크립트 코드·생성 파일 내용·동작 원리를 직접 따라하며 확인하려면:

**[→ HOL_step_by_step.md](./HOL_step_by_step.md)**

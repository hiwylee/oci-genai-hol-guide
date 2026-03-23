# OCI GenAI Hands-on Lab 가이드

## 이 실습은 무엇인가요?

이 HOL에서는 **OCI Generative AI** 서비스를 활용한 **RAG(Retrieval-Augmented Generation) 챗봇 플랫폼**을 처음부터 직접 구축합니다.

단순한 API 호출 실습이 아니라, 실제 서비스에 가까운 구성 — LLM API 프록시, 웹 채팅 UI, Oracle DB 벡터 저장소 — 을 컨테이너로 직접 배포하고 동작을 확인합니다.

---

## 완성되는 아키텍처

```
┌──────────────────────────────────────────────────────────────────────────┐
│  참가자 PC 브라우저                                                        │
│  http://<인스턴스_IP>:8080                                                │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTP
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  OCI Compute Instance (Oracle Linux 8)                                   │
│                                                                          │
│  ┌─────────────────────┐  hol-net   ┌──────────────────────────────────┐ │
│  │  open-webui         │◄──────────►│  oci-genai-access-gateway        │ │
│  │  :8080              │  컨테이너  │  :8088                           │ │
│  │                     │  DNS 통신  │                                  │ │
│  │  ▪ 채팅 인터페이스  │            │  ▪ OpenAI API 호환 레이어       │ │
│  │  ▪ RAG 파이프라인   │            │  ▪ OCI GenAI SDK 호출           │ │
│  │  ▪ 문서 업로드·검색 │            │  ▪ API Key: ocigenerativeai     │ │
│  └──────────┬──────────┘            └──────────────┬───────────────────┘ │
│             │ Oracle DB (Wallet TLS)               │ HTTPS               │
└─────────────┼─────────────────────────────────── ──│─────────────────────┘
              │                                      │
              ▼                                      ▼
┌─────────────────────────┐         ┌────────────────────────────────────┐
│  Oracle ADW             │         │  OCI Generative AI                 │
│  (ap-chuncheon-1)       │         │  (us-chicago-1)                    │
│                         │         │                                    │
│  ▪ 메타데이터 DB        │         │  ▪ LLM: meta.llama, cohere, xai   │
│    사용자·채팅·모델     │         │  ▪ Embedding: cohere.embed-v4.0   │
│  ▪ 벡터 저장소 (RAG)    │         │  ▪ 34개+ 모델 지원                │
└─────────────────────────┘         └────────────────────────────────────┘
```

---

## 구성 요소 설명

### OCI GenAI Access Gateway
- GitHub: [hiwylee/OCI_GenAI_access_gateway](https://github.com/hiwylee/OCI_GenAI_access_gateway)
- OCI Generative AI API는 자체 형식(OCI SDK)을 사용합니다.
- Gateway는 이를 **OpenAI API 호환 형식**으로 변환하는 프록시 역할을 합니다.
- Open-WebUI 등 OpenAI API를 지원하는 모든 도구에서 OCI GenAI를 사용 가능하게 합니다.
- FastAPI + Gunicorn으로 구현, Podman 컨테이너로 실행

### Open-WebUI
- GitHub: [open-webui/open-webui](https://github.com/open-webui/open-webui)
- LLM 채팅, 파일 업로드, RAG, 모델 관리 기능을 제공하는 웹 UI
- `OPENAI_API_BASE_URL`을 Gateway로 지정해 OCI GenAI와 연동
- Oracle ADW를 벡터 저장소와 메타데이터 DB로 사용

### Oracle Autonomous Data Warehouse (ADW)
- **메타데이터 DB**: 사용자 계정, 채팅 기록, 모델 설정 저장
- **벡터 저장소**: 업로드한 문서를 임베딩(cohere.embed-v4.0)해 저장, RAG 검색에 사용
- Wallet 파일로 TLS 인증 접속 (비밀번호 노출 없이 안전하게 연결)

### Podman 컨테이너 네트워크 (hol-net)
- `open-webui`와 `oci-genai-access-gateway`가 **hol-net** 네트워크를 공유
- 같은 네트워크 안에서 컨테이너명이 DNS로 동작 → `http://oci-genai-access-gateway:8088/v1`
- `localhost:8088` 사용 불가 (컨테이너 간 통신은 컨테이너명 DNS 사용)

---

## 리전 구성

| 리전 | 식별자 | 용도 |
|------|--------|------|
| 한국 춘천 | `ap-chuncheon-1` | OCI CLI 홈리전, IAM, ADW |
| 미국 시카고 | `us-chicago-1` | OCI Generative AI 서비스 |

> Gateway `config.py`의 `REGION = "us-chicago-1"` 설정이 GenAI API 호출 리전을 결정합니다.
> OCI CLI(`~/.oci/config`)의 `region`은 IAM·ADW용 홈리전(춘천)입니다.

---

## 사전 준비사항 (선택 설치)

> `git`과 `podman`은 VM 생성 시 자동으로 설치됩니다. 아래는 실습 중 직접 개발·운영이 필요한 경우의 선택 설치 가이드입니다.

### uv / nvm

```bash
# uv (Python 패키지 관리자)
curl -LsSf https://astral.sh/uv/install.sh | sh

# nvm (Node.js 버전 관리자)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
```

### Node.js 22.x

```bash
source ~/.bashrc
nvm list-remote | grep v22
nvm install 22
nvm use 22
```

### Java / SQLcl

```bash
sudo dnf install jdk-24-headless.x86_64 -y
sudo dnf install sqlcl -y
```

### 추가 포트 오픈 (MCPO 등 선택 서비스)

기본 포트(8080, 8088)는 `setup.sh`에서 자동으로 오픈됩니다. 추가 서비스가 필요한 경우:

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp   # OpenWebUI 대체 포트
sudo firewall-cmd --permanent --add-port=8000/tcp   # MCPO
sudo firewall-cmd --reload
```

---

## 실습 진행 순서

### 1단계: 실습 환경 자동 구성

SSH 접속 후 아래 명령 한 줄로 전체 환경을 구성합니다.

```bash
cd ~/hol && ./setup.sh
```

11단계가 자동 실행됩니다 (약 5~10분):

| 단계 | 내용 |
|------|------|
| 1 | 환경 변수 로드 (`variables.sh`) |
| 2 | uv 설치 (Python 패키지 관리자) |
| 3 | OCI CLI 인증 설정 (`~/hol/.oci/config`) |
| 4 | ADW Wallet 준비 (`~/hol/wallet/`) |
| 5 | Gateway 소스 clone (GitHub) |
| 6 | Gateway `config.py` 생성 (GenAI 리전 설정) |
| 7 | Gateway 컨테이너용 OCI config 준비 |
| 8 | Open-WebUI `.env` 생성 |
| 9 | 방화벽 포트 오픈 + 컨테이너 지속성(linger) 설정 |
| 10 | Gateway 이미지 빌드 + 컨테이너 실행 |
| 11 | Open-WebUI 컨테이너 실행 + 헬스체크 |

### 2단계: 서비스 접속

설정 완료 후 출력되는 URL로 브라우저에서 접속합니다.

```
Open-WebUI: http://<인스턴스_PUBLIC_IP>:8080
Gateway   : http://<인스턴스_PUBLIC_IP>:8088/health
```

### 3단계: Open-WebUI 초기 설정

1. 브라우저에서 `http://<IP>:8080` 접속
2. **첫 접속 시 관리자 계정 생성** (이름, 이메일, 비밀번호 입력)
3. **Settings → Connections** 에서 OpenAI API 연결 확인
   - URL: `http://oci-genai-access-gateway:8088/v1` (자동 설정)
   - Key: `ocigenerativeai` (자동 설정)
4. 상단 모델 선택 → OCI GenAI 모델 선택 → 채팅 시작

### 4단계: RAG 실습

1. **Documents** 메뉴 → 파일 업로드 (PDF, TXT, DOCX 등)
2. 채팅창에서 `#문서명` 선택 후 질문 → 문서 내용 기반 답변 확인
3. 임베딩 모델: `cohere.embed-v4.0` (us-chicago-1, 1024차원)

---

## 서비스 상태 확인 명령

```bash
# 실행 중인 컨테이너 확인
podman ps

# Gateway 헬스체크
curl http://localhost:8088/health
# 예상: {"status":"OK"}

# 사용 가능한 모델 목록 (Bearer 토큰 필수)
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

# 개인키 존재 확인
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

# Linger 활성화 (비활성화된 경우)
sudo loginctl enable-linger opc

# 컨테이너 재시작
podman start oci-genai-access-gateway open-webui
```

---

## 참고 자료

| 자료 | URL |
|------|-----|
| OCI Generative AI | https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm |
| OCI GenAI Access Gateway | https://github.com/hiwylee/OCI_GenAI_access_gateway |
| Open-WebUI | https://github.com/open-webui/open-webui |
| Oracle ADW | https://docs.oracle.com/en-us/iaas/autonomous-database/ |
| Podman | https://docs.podman.io/ |

---

---

## 단계별 상세 가이드

각 단계를 직접 손으로 실행하면서 내부 동작을 이해하고 싶다면 아래 가이드를 참고하세요.

**[→ 단계별 상세 실행 가이드 (step_by_step.md)](./step_by_step.md)**

주요 내용:
- 각 단계의 스크립트 코드 + 직접 실행 명령
- 생성되는 파일 예시 (config, .env, sqlnet.ora 등)
- 각 설정이 필요한 이유 설명
- 최종 헬스체크 및 문제 해결 방법

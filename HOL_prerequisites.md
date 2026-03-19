# OCI GenAI HOL 사전 준비 가이드

이 문서는 실습 당일 원활한 진행을 위해 **미리 읽어두어야 할 개념과 환경 준비 사항**을 정리합니다.

---

## 0. 이 문서의 목적

OCI GenAI HOL은 처음 OCI를 접하는 분도 참여할 수 있도록 설계되어 있지만,
아래 개념을 미리 알고 오시면 실습 시간을 훨씬 효율적으로 사용할 수 있습니다.

| 이 문서에서 다루는 것 | 이 문서에서 다루지 않는 것 |
|----------------------|--------------------------|
| 개념 이해 및 배경 지식 | 실제 명령어 실행 순서 |
| PC 환경 사전 준비 | 상세 실습 절차 |
| 자주 발생하는 혼동 포인트 | 코드 구현 상세 |

실습 절차는 **[HOL_step_by_step.md](./HOL_step_by_step.md)** 를 참조하세요.

---

## 1. PC 환경 요구사항

### 필수 소프트웨어

| 항목 | 요구 사항 | 비고 |
|------|-----------|------|
| **웹 브라우저** | Chrome, Firefox, Edge 최신 버전 | Safari 가능하나 Chrome 권장 |
| **SSH 클라이언트** | 아래 표 참조 | VM 접속에 필수 |
| **인터넷 연결** | 방화벽이 TCP 8080, 8088 포트 허용 | 사내망 사용 시 IT 부서 확인 필요 |

### SSH 클라이언트 설치

| OS | 권장 도구 | 대안 |
|----|-----------|------|
| **Windows** | [MobaXterm](https://mobaxterm.mobatek.net/) Home Edition (무료) | PuTTY |
| **macOS** | 내장 Terminal (별도 설치 불필요) | iTerm2 |
| **Linux** | 내장 Terminal (별도 설치 불필요) | — |

> **MobaXterm 권장 이유**: SSH 키 파일 관리, 탭, 파일 브라우저를 한 화면에서 처리할 수 있어
> PuTTY보다 편리합니다.

### 사전 확인 사항

실습 전 다음을 미리 확인하세요:

- [ ] SSH 클라이언트 설치 완료
- [ ] 브라우저에서 외부 IP의 8080 포트 접속 가능 여부 (사내망 사용 시 확인)
- [ ] 강사로부터 `환경 변수 파일`과 `SSH 접속 키` 수령

---

## 2. SSH 접속 방법

실습 VM은 OCI Compute 인스턴스(Oracle Linux 9)입니다.
비밀번호 대신 **SSH 키 파일**로 접속합니다.

### Windows — MobaXterm

1. MobaXterm 실행 → **Session** 클릭
2. **SSH** 탭 선택
3. 다음 항목 입력:
   - **Remote host**: 강사가 알려준 VM 공인 IP
   - **Username**: `opc`
   - **Port**: `22`
4. **Advanced SSH settings** 탭 → **Use private key** 체크 → 강사 제공 `ssh-hol.key` 파일 선택
5. **OK** 클릭 → 접속

```
# 접속 정보 요약
호스트(Host): <강사 제공 VM IP>
사용자(User): opc
포트(Port):   22
인증 방식:    SSH 개인키 (비밀번호 없음)
키 파일:      ssh-hol.key (강사 제공)
```

### macOS / Linux — Terminal

강사가 제공한 `ssh-hol.key` 파일을 적절한 위치에 저장한 후:

```bash
# 키 파일 권한 설정 (최초 1회)
chmod 400 ~/Downloads/ssh-hol.key

# SSH 접속
ssh -i ~/Downloads/ssh-hol.key opc@<VM_IP>
```

> **권한 오류가 나는 이유**: SSH는 보안상 개인키 파일의 권한이 너무 열려 있으면 접속을 거부합니다.
> `chmod 400`으로 소유자 읽기 전용으로 설정해야 합니다.

### 접속 확인

접속 성공 시 아래와 같은 프롬프트가 나타납니다:

```
[opc@hol-user01 ~]$
```

접속 후 실습 디렉터리 확인:

```bash
ls ~/hol/
```

---

## 3. OCI 핵심 개념

### Tenancy (테넌시)

OCI에서 **조직 단위**입니다. 회사 또는 팀이 사용하는 OCI 계정 전체를 가리킵니다.
모든 리소스(VM, DB, 네트워크 등)는 하나의 Tenancy 아래에 속합니다.

```
Tenancy (HOL 운영 조직 전체)
└── Compartment (HOL 실습 공간)
    ├── Compute Instance (참가자 VM)
    └── Autonomous Database (ADW)
```

### Compartment (컴파트먼트)

**리소스 격리 단위**입니다. 폴더와 유사하게, 관련 리소스를 묶어 관리하고 접근을 제어합니다.

- 이 HOL에서는 강사가 미리 Compartment를 생성하고, 참가자 VM과 ADW를 그 안에 배치합니다.
- 참가자는 본인 Compartment 내 리소스만 접근할 수 있습니다.

### IAM (Identity and Access Management)

**누가 무엇을 할 수 있는지** 정의하는 체계입니다.

| 구성 요소 | 역할 | HOL에서의 예 |
|-----------|------|-------------|
| **User** | 개별 계정 | `hol_user01`, `hol_user02` |
| **Group** | 사용자 묶음 | `hol_group` |
| **Policy** | 그룹의 권한 정의 | "hol_group은 hol_compartment에서 GenAI 사용 가능" |

### 리전(Region) — 왜 2개인가?

이 HOL에서는 두 리전을 동시에 사용합니다.

| 리전 | 식별자 | 용도 |
|------|--------|------|
| 한국 춘천 | `ap-chuncheon-1` | IAM 인증, OCI CLI, ADW (홈 리전) |
| 미국 시카고 | `us-chicago-1` | OCI Generative AI 서비스 |

**홈 리전(ap-chuncheon-1)이 필요한 이유**: IAM(사용자·정책) 및 ADW는 테넌시의 홈 리전에서 관리됩니다.

**시카고 리전(us-chicago-1)이 필요한 이유**: OCI Generative AI 서비스는 특정 리전에서만 제공됩니다.
현재 한국 리전에서는 GenAI를 지원하지 않기 때문에 시카고 리전의 API를 사용합니다.

> 이 때문에 OCI 인증 설정 파일(`config`)이 2개 필요합니다. 자세한 내용은 [4절](#4-oci-인증체계-중요)을 참조하세요.

---

## 4. OCI 인증체계 (중요)

수강생이 가장 많이 혼동하는 부분입니다. 차근차근 이해하면 실습 오류의 80%를 예방할 수 있습니다.

### API Key 인증 방식

OCI API를 호출할 때 사용하는 기본 인증 방식입니다.
**RSA 공개키/개인키 쌍**을 사용합니다.

```
[내 PC / VM]                         [OCI API 서버]
    │                                      │
    │  1. 개인키(oci_api_key.pem)로 서명   │
    │──────────────────────────────────►   │
    │  2. OCI가 등록된 공개키로 서명 검증   │
    │◄──────────────────────────────────   │
    │  3. 인증 성공 → API 응답 반환         │
```

강사는 HOL 준비 과정에서:
1. 각 참가자의 RSA 키 쌍을 생성
2. 공개키를 OCI IAM에 등록 (API Key 등록)
3. 개인키(`oci_api_key.pem`)와 설정 파일을 참가자 VM에 배포

### OCI Config 파일 구조

OCI SDK/CLI가 API 호출 시 참조하는 인증 정보 파일입니다.

```ini
[DEFAULT]
user=ocid1.user.oc1..aaaa...         # 내 사용자 OCID
fingerprint=ab:cd:ef:...:12          # 공개키 지문 (등록된 키 확인용)
tenancy=ocid1.tenancy.oc1..aaaa...   # 테넌시 OCID
region=ap-chuncheon-1                # 기본 리전
key_file=/home/opc/hol/.oci/oci_api_key.pem  # 개인키 파일 경로
```

**OCID란?** OCI 리소스 식별자(OCI Resource Identifier)로, 모든 OCI 리소스에 부여되는 고유 ID입니다.
형식: `ocid1.<리소스유형>.<리전코드>..<고유문자열>`

### HOL에서 Config 파일이 2개인 이유

```
~/hol/
├── .oci/
│   └── config         ← 호스트용 (ap-chuncheon-1)
└── oci_genai_gateway/
    └── .oci/
        └── config     ← Gateway 컨테이너용 (us-chicago-1)
```

| 파일 위치 | 리전 | 사용 목적 |
|-----------|------|-----------|
| `~/hol/.oci/config` | `ap-chuncheon-1` (춘천) | OCI CLI 명령어, ADW Wallet 다운로드 |
| `~/hol/oci_genai_gateway/.oci/config` | `us-chicago-1` (시카고) | Gateway가 OCI GenAI API 호출 |

> Gateway 컨테이너는 `~/hol/oci_genai_gateway/.oci/` 디렉터리를
> 컨테이너 내부의 `/root/.oci/`로 마운트합니다.
> 따라서 컨테이너용 config의 `key_file` 경로는 `/root/.oci/oci_api_key.pem` (컨테이너 내부 경로) 입니다.

### 인증 3가지 방식 비교

| 방식 | 설명 | HOL에서 사용 여부 |
|------|------|-------------------|
| **API_KEY** | config 파일 + 개인키 파일 조합 | **YES** (기본) |
| **INSTANCE_PRINCIPAL** | OCI Compute VM 자체가 인증 주체 (키 파일 불필요) | 고급 사용자용 |
| **RESOURCE_PRINCIPAL** | OCI Functions 등 서버리스 환경용 (키 파일 불필요) | HOL 미사용 |

이 HOL은 **API_KEY** 방식을 사용합니다. 강사가 모든 키 파일을 미리 배포했으므로, 참가자가 직접 키를 생성할 필요는 없습니다.

### Bearer Token vs OCI 인증 — 혼동 주의

이 HOL에서는 두 가지 종류의 "인증"이 등장합니다. 혼동하지 마세요.

| 구분 | 값 | 사용 위치 | 용도 |
|------|-----|-----------|------|
| **OCI API 인증** | 개인키 파일(`oci_api_key.pem`) | `~/.oci/config` | OCI 서비스에 내 신원 증명 |
| **Gateway Bearer Token** | `ocigenerativeai` (문자열) | HTTP 헤더 `Authorization: Bearer ocigenerativeai` | Open-WebUI → Gateway 간 접근 제어 |

Gateway Bearer Token은 OCI와 무관한, Gateway 내부에서만 사용하는 간단한 API 키입니다.

### 흔한 인증 오류 3가지

**오류 1: `NotAuthenticated` 또는 `401`**
```
원인: config 파일의 fingerprint 또는 key_file 경로 불일치
확인: cat ~/hol/oci_genai_gateway/.oci/config
      ls -la ~/hol/oci_genai_gateway/.oci/oci_api_key.pem
```

**오류 2: `NotAuthorized` 또는 `403`**
```
원인: IAM Policy 미설정 또는 Compartment OCID 오류
확인: cat ~/hol/oci_genai_gateway/app/config.py
      → OCI_COMPARTMENT 값이 올바른지 확인
```

**오류 3: `Can not connect to OCI` — Gateway 기동 직후**
```
원인: 컨테이너 내부의 key_file 경로가 /root/.oci/ 가 아닌 경우
확인: cat ~/hol/oci_genai_gateway/.oci/config
      → key_file=/root/.oci/oci_api_key.pem 인지 확인
      (컨테이너 내부 경로이므로 /home/opc/... 이면 안 됨)
```

---

## 5. OCI Generative AI 개념

### OCI Generative AI 서비스란?

Oracle Cloud Infrastructure에서 제공하는 **관리형 LLM(대규모 언어 모델) 서비스**입니다.
별도 GPU 서버 없이 API 호출만으로 LLM과 임베딩 모델을 사용할 수 있습니다.

서비스 엔드포인트: `https://inference.generativeai.us-chicago-1.oci.oraclecloud.com`

### 지원 모델 (주요)

| 유형 | 모델 예시 | 특징 |
|------|-----------|------|
| **LLM (대화)** | `meta.llama-3.3-70b-instruct` | 범용 대화, 한국어 지원 |
| **LLM (대화)** | `cohere.command-r-plus-08-2024` | 긴 컨텍스트, 도구 호출 지원 |
| **Embedding** | `cohere.embed-v4.0` | 1024차원 벡터, RAG용 |

HOL 환경에서는 34개 이상의 모델을 사용할 수 있습니다.

### OpenAI API 호환성 — 왜 Gateway가 필요한가?

```
Open-WebUI          Gateway              OCI GenAI
(OpenAI 형식)  →  (변환 레이어)  →  (OCI SDK 형식)

POST /v1/chat/completions              OCI GenAI Python SDK 호출
{                          변환         GenerativeAiInference.chat(...)
  "model": "meta.llama...",    ──────►  CompartmentId: ...
  "messages": [...]                    Model: meta.llama...
}                                      Messages: ...
```

Open-WebUI를 비롯한 대부분의 LLM 도구는 **OpenAI API 형식**(`/v1/chat/completions`)을 표준으로 사용합니다.
OCI GenAI는 자체 SDK 형식을 사용하므로, **Gateway(프록시)** 가 두 형식 사이를 변환합니다.

---

## 6. Oracle ADW 개념

### Autonomous Database (ADB-S)란?

Oracle이 제공하는 **완전 관리형 클라우드 데이터베이스**입니다.
튜닝, 패치, 백업을 자동으로 처리하므로 DBA 없이도 운영할 수 있습니다.

이 HOL에서 사용하는 것은 **ADB-S (Autonomous Data Warehouse, Serverless)** 형태입니다.
Oracle Database 23ai를 기반으로 하며, AI Vector Search를 기본 지원합니다.

### Wallet — 왜 필요한가?

ADW는 **TLS(전송 계층 보안)** 기반으로만 접속을 허용합니다.
단순 비밀번호만으로는 연결할 수 없고, **Wallet** 이라는 인증서 묶음이 필요합니다.

```
Wallet 디렉터리 (~/hol/wallet/)
├── cwallet.sso       ← SSO 기반 자동 로그인용 인증서 (바이너리)
├── ewallet.p12       ← PKCS#12 형식 인증서 (바이너리)
├── tnsnames.ora      ← 접속 주소(DSN) 정의 텍스트 파일
└── sqlnet.ora        ← Wallet 경로 설정 텍스트 파일
```

> 바이너리 파일(`*.sso`, `*.p12`)은 강사가 미리 배포합니다.
> 텍스트 파일(`tnsnames.ora`, `sqlnet.ora`)은 setup.sh 실행 시 참가자 환경에 맞게 자동 생성됩니다.

### ADW의 이중 역할

이 HOL에서 ADW는 하나의 DB가 두 가지 역할을 동시에 수행합니다:

```
Oracle ADW
├── 메타데이터 저장소 (DB 유저: hol_user01-meta)
│   ├── 사용자 계정 테이블
│   ├── 채팅 기록 테이블
│   └── 모델/설정 테이블
│
└── 벡터 저장소 (DB 유저: hol_user01)
    └── 문서 임베딩 벡터 (AI Vector Search)
        → RAG 검색에 사용
```

### DSN 프로필

`tnsnames.ora`에는 같은 ADW에 대해 성능 수준이 다른 여러 접속 프로필이 정의됩니다.

| 프로필 | 병렬 처리 | 권장 사용 사례 |
|--------|-----------|--------------|
| `low` | 낮음 | 단순 조회, 가벼운 작업 |
| `medium` | 중간 | **HOL 기본 사용** |
| `high` | 높음 | 대용량 분석, 배치 |

HOL에서는 `medium` 프로필(`HOL_ADB_DSN=medium`)을 기본으로 사용합니다.

---

## 7. RAG 개념

### RAG란?

**RAG(Retrieval-Augmented Generation)** 는 LLM의 답변을 외부 문서 기반으로 보강하는 기법입니다.

**LLM만 사용할 때의 한계**:
- 학습 데이터 이후의 최신 정보를 모름
- 사내 문서, 비공개 정보에 대해 답변 불가
- 근거 없이 그럴듯한 오답을 생성하는 Hallucination 문제

**RAG로 해결**:
- 내 문서를 벡터 DB에 저장
- 질문과 의미적으로 유사한 문서 조각을 검색
- LLM이 검색된 문서를 참고해 답변 생성

### 임베딩 파이프라인 (문서 저장)

```
문서 업로드
    │
    ▼
청크 분할 (긴 문서 → 작은 조각으로 분할)
    │
    ▼
임베딩 모델 호출: cohere.embed-v4.0
(텍스트 → 1024차원 숫자 벡터)
    │
    ▼
Oracle ADW AI Vector Search에 저장
```

### 검색 흐름 (질문 처리)

```
사용자 질문
    │
    ▼
질문 → 임베딩 벡터 변환 (cohere.embed-v4.0)
    │
    ▼
Oracle ADW에서 유사도 검색 (벡터 거리 계산)
    │
    ▼
관련 문서 조각 추출
    │
    ▼
LLM에 [질문 + 관련 문서] 함께 전달
    │
    ▼
LLM이 문서 기반으로 답변 생성
```

### Open-WebUI에서의 RAG 실습 흐름

1. 브라우저에서 `http://<VM IP>:8080` 접속
2. **Documents** 메뉴 → PDF, TXT, DOCX 등 파일 업로드
3. 채팅창에서 `#문서명` 입력 후 질문
4. 업로드한 문서 내용을 기반으로 한 답변 수신

> 임베딩은 자동으로 처리됩니다. 수동으로 벡터 변환 명령을 실행할 필요가 없습니다.

---

## 8. 실습 아키텍처 이해

### 전체 구조

```
┌──────────────────────────────────────────────────────────────────────┐
│  내 PC 브라우저                                                        │
│  http://<VM IP>:8080                                                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  OCI Compute Instance (내 VM · Oracle Linux 9)                        │
│                                                                      │
│  ┌────────────────────┐  hol-net  ┌───────────────────────────────┐  │
│  │  open-webui        │◄─────────►│  oci-genai-access-gateway     │  │
│  │  :8080             │  컨테이너  │  :8088                        │  │
│  │                    │  DNS 통신 │                               │  │
│  │  · 채팅 UI          │           │  · OpenAI API 호환 프록시     │  │
│  │  · RAG 파이프라인   │           │  · OCI GenAI SDK 호출         │  │
│  │  · 문서 업로드·검색  │           │  · Bearer Token 검증          │  │
│  └────────┬───────────┘           └──────────────┬────────────────┘  │
│           │ Oracle DB (Wallet TLS)               │ HTTPS             │
└───────────┼─────────────────────────────────────┼───────────────────┘
            │                                      │
            ▼                                      ▼
┌─────────────────────────┐       ┌──────────────────────────────────┐
│  Oracle ADW             │       │  OCI Generative AI               │
│  (ap-chuncheon-1)       │       │  (us-chicago-1)                  │
│                         │       │                                  │
│  · 메타데이터 DB          │       │  · LLM: meta.llama, cohere 등   │
│  · 벡터 저장소 (RAG)     │       │  · Embedding: cohere.embed-v4.0 │
└─────────────────────────┘       └──────────────────────────────────┘
```

### 컴포넌트 역할 요약

| 컴포넌트 | 역할 | 실행 위치 |
|----------|------|-----------|
| **Open-WebUI** | 채팅 UI, 파일 업로드, RAG, 모델 관리 | 내 VM (Podman 컨테이너, 포트 8080) |
| **OCI GenAI Access Gateway** | OCI GenAI API ↔ OpenAI 형식 변환 프록시 | 내 VM (Podman 컨테이너, 포트 8088) |
| **Oracle ADW** | 메타데이터 DB + 벡터 저장소 | OCI 춘천 리전 |
| **OCI Generative AI** | LLM 추론, 임베딩 API | OCI 시카고 리전 |

### Podman hol-net 네트워크

Open-WebUI와 Gateway는 같은 VM에서 **별개의 컨테이너**로 실행됩니다.
컨테이너끼리 통신하려면 공유 네트워크가 필요합니다.

```
hol-net (Podman 브릿지 네트워크)
├── open-webui 컨테이너
│     → "oci-genai-access-gateway:8088" 으로 Gateway 접근 가능
└── oci-genai-access-gateway 컨테이너
      → 컨테이너명이 DNS 이름으로 자동 동작
```

**왜 `localhost:8088`이 아닌가?** Open-WebUI 컨테이너 안에서 `localhost`는 Open-WebUI 컨테이너 자신을 가리킵니다.
다른 컨테이너(Gateway)에 접근하려면 `hol-net` 안에서 **컨테이너명**(`oci-genai-access-gateway`)을 DNS로 사용해야 합니다.

---

## 9. 실습 시작 전 체크리스트

실습 당일 아래 항목을 순서대로 확인하세요.

### 사전 준비 (실습 전날까지)

- [ ] SSH 클라이언트 설치 완료 (Windows: MobaXterm, Mac/Linux: 기본 Terminal)
- [ ] 강사로부터 다음 자료 수령:
  - [ ] SSH 접속 키 파일 (`ssh-hol.key`)
  - [ ] VM 공인 IP 주소
  - [ ] OCI 환경 변수 파일 (`variables.sh`)

### 당일 확인 (실습 시작 시)

- [ ] SSH로 VM 접속 성공 (`ssh -i ssh-hol.key opc@<VM_IP>`)
- [ ] `ls ~/hol/` 명령으로 홈 디렉터리 파일 확인
- [ ] 브라우저에서 `http://<VM_IP>:8080` 접속 가능 여부 확인 (setup.sh 실행 후)

### HOL 진행 중 주의사항

| 금지 사항 | 이유 |
|-----------|------|
| ADW, VM 등 리소스 임의 삭제 | 다른 참가자의 실습에 영향을 줄 수 있음 |
| API 개인키 파일 외부 공유 | HOL 전용 키이나 OCI 계정 보안 위협 |
| 비밀번호(`HOL_DB_PASSWORD`) 공유 | DB 데이터 보호 |
| 실습과 무관한 OCI 리소스 생성 | 불필요한 비용 발생 |

### 실습 완료 기준

- [ ] `podman ps` 명령 실행 시 `open-webui`, `oci-genai-access-gateway` 두 컨테이너 모두 `Up` 상태
- [ ] `curl http://localhost:8088/health` 응답이 `{"status":"OK"}`
- [ ] 브라우저에서 `http://<VM_IP>:8080` 접속 후 관리자 계정 생성 완료
- [ ] OCI GenAI 모델 선택 후 채팅 메시지 1건 이상 주고받기 성공
- [ ] (선택) 문서 업로드 후 RAG 기반 답변 확인

---

## 참고 자료

| 자료 | 링크 |
|------|------|
| OCI Generative AI 공식 문서 | https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm |
| OCI API Key 인증 공식 문서 | https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm |
| Oracle ADW 공식 문서 | https://docs.oracle.com/en-us/iaas/autonomous-database/ |
| Open-WebUI GitHub | https://github.com/open-webui/open-webui |
| MobaXterm 다운로드 | https://mobaxterm.mobatek.net/ |

---

**단계별 실습 명령어는** [HOL_step_by_step.md](./HOL_step_by_step.md) **를 참조하세요.**

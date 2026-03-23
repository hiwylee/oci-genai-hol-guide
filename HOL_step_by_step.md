# OCI GenAI HOL — 단계별 상세 실습 가이드

---

## 이 실습에서 무엇을 만드나요?

이 HOL의 목표는 세 가지 핵심 구성 요소를 직접 구축해 연결하는 것입니다.

```
브라우저
  │
  ▼
[핵심 3] Open-WebUI          ─── hol-net ───  [핵심 1] OCI GenAI Gateway
  채팅 UI / RAG / 문서 업로드                       OCI GenAI API 프록시
  │                                                     │
  ▼                                                     ▼
[핵심 2] Oracle ADW                              OCI Generative AI
  메타데이터 DB + 벡터 저장소                       LLM / Embedding
```

| 핵심 구성 요소 | 만드는 이유 |
|---------------|------------|
| **OCI GenAI Gateway** | OCI GenAI API는 자체 형식을 사용합니다. 이것을 Open-WebUI 등 일반 도구가 이해하는 OpenAI 호환 형식으로 변환하는 프록시가 필요합니다. |
| **Oracle ADW 연결** | 채팅 기록, 사용자 정보를 DB에 저장하고, 업로드한 문서를 벡터로 저장해 RAG 검색에 사용합니다. |
| **Open-WebUI** | 브라우저에서 LLM과 대화하고, 문서를 업로드해 RAG 기반 답변을 받는 웹 인터페이스입니다. |

> **자동 실행**: `cd ~/hol && ./setup.sh` (약 10분)
> **이 문서**: 각 단계를 직접 실행하며 내부 동작을 이해합니다.

---

## 전체 작업 흐름

```
[사전 준비]
  └─ 환경 변수 로드 · Python 도구 설치

[핵심 1: Gateway 구축]
  ├─ (부수) OCI 인증 설정    ← Gateway가 OCI API를 호출하려면 인증이 필요
  ├─ (부수) 소스 코드 Clone  ← FastAPI 애플리케이션 소스
  ├─ (부수) config.py 생성  ← 어느 리전의 GenAI를 쓸지 지정
  └─ [실행] 컨테이너 빌드 + 기동

[핵심 2: Oracle ADW 연결]
  └─ (부수) Wallet 파일 준비 ← TLS 접속 인증서

[핵심 3: Open-WebUI 구축]
  ├─ (부수) .env 파일 생성  ← Gateway URL, DB 접속 정보 주입
  └─ [실행] 컨테이너 pull + 기동

[인프라]
  └─ 방화벽 포트 오픈 · 서비스 지속성(Linger) 설정

[검증]
  └─ 헬스체크 · 브라우저 접속 확인
```

---

## 시작 전 확인 — 디렉터리 구조

```bash
ls ~/hol/
```

예상 출력:
```
.oci/              # 내 OCI API 개인키 (강사 배포)
templates/         # 설정 파일 템플릿 모음 (강사 배포)
variables.sh       # 내 환경 변수 (강사가 미리 설정)
setup.sh           # one-click 실행 스크립트
wallet/            # ADW Wallet 바이너리 (강사 배포)
```

> `open-webui/`와 `oci_genai_gateway/` 디렉터리는 setup 과정에서 생성됩니다.

---

## 사전 준비 — 실습 환경 초기화

이후 모든 작업의 기반이 되는 변수와 도구를 준비합니다.

### Step 0 · variables.sh 내용 확인

실습에 사용되는 내 계정 정보를 확인합니다. 강사가 미리 설정해 두었습니다.

```bash
cat ~/hol/variables.sh
```

| 변수 | 설명 | 예시 |
|------|------|------|
| `HOL_USER_OCID` | 내 OCI 사용자 OCID | `ocid1.user.oc1..aaaa...` |
| `HOL_TENANCY_OCID` | OCI 테넌시 OCID | `ocid1.tenancy.oc1..aaaa...` |
| `HOL_COMPARTMENT_OCID` | HOL Compartment OCID | `ocid1.compartment.oc1..aaaa...` |
| `HOL_FINGERPRINT` | API Key fingerprint | `ab:cd:ef:...:12` |
| `HOL_HOME_REGION` | OCI CLI 홈리전 | `ap-chuncheon-1` |
| `HOL_REGION` | GenAI 서비스 리전 | `us-chicago-1` |
| `HOL_KEY_FILE` | API 개인키 경로 | `/home/opc/hol/.oci/oci_api_key.pem` |
| `HOL_USER` | DB 사용자명 | `hol_user01` |
| `HOL_DB_PASSWORD` | DB 비밀번호 | `WElCome123###` |
| `HOL_ADB_DSN` | ADB 접속 DSN | `medium` |
| `HOL_WALLET_DIR` | Wallet 경로 | `/home/opc/hol/wallet` |

### Step 1 · 변수 로드

```bash
source ~/hol/variables.sh

# 로드 확인
echo "사용자: ${HOL_USER}  /  GenAI 리전: ${HOL_REGION}"
```

> `source`는 파일 안의 `export` 변수를 현재 셸 세션에 등록합니다.
> 이후 모든 단계에서 `${HOL_USER}` 같은 변수를 그대로 사용합니다.

### Step 2 · uv 설치

Python 패키지 관리자를 설치합니다. 이미 설치된 경우 건너뜁니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="${HOME}/.local/bin:${PATH}"

uv --version  # 설치 확인
```

---

## [핵심 1] OCI GenAI Gateway 구축

**목표**: OCI GenAI API를 OpenAI 호환 형식으로 변환하는 프록시 서버를 배포합니다.

Open-WebUI 등 대부분의 LLM 도구는 OpenAI API 형식을 기준으로 동작합니다.
OCI GenAI는 자체 SDK 형식을 사용하기 때문에, 중간에서 형식을 변환해 주는
**Gateway(프록시 서버)** 가 필요합니다.

```
Open-WebUI  →  POST /v1/chat/completions  →  Gateway  →  OCI GenAI SDK 호출  →  OCI GenAI
              (OpenAI 형식)                            (OCI 형식으로 변환)
```

Gateway는 FastAPI로 구현되어 있으며, Podman 컨테이너로 실행됩니다.

---

### (부수) Step 3 · OCI 인증 설정

**왜 필요한가**: Gateway가 OCI GenAI API를 호출하려면 내 OCI 계정 인증 정보가 필요합니다.
인증 파일은 두 곳에 필요합니다: 호스트(OCI CLI용)와 Gateway 컨테이너 내부(API 호출용).

**호스트용 OCI CLI config 생성**

```bash
mkdir -p ~/hol/.oci

envsubst < ~/hol/templates/HOL_Guide/.oci/config.template > ~/hol/.oci/config
chmod 600 ~/hol/.oci/config
export OCI_CLI_CONFIG_FILE=~/hol/.oci/config
```

생성되는 `~/hol/.oci/config`:
```ini
[DEFAULT]
user=ocid1.user.oc1..aaaa...       # HOL_USER_OCID
fingerprint=ab:cd:ef:...:12        # HOL_FINGERPRINT
tenancy=ocid1.tenancy.oc1..aaaa... # HOL_TENANCY_OCID
region=ap-chuncheon-1              # HOL_HOME_REGION (IAM·ADW 홈리전)
key_file=/home/opc/hol/.oci/oci_api_key.pem
```

검증:
```bash
oci iam user get --user-id "${HOL_USER_OCID}" --query 'data.name' --raw-output
```

**Gateway 컨테이너용 OCI config 복사**

Gateway 컨테이너는 OCI GenAI API를 직접 호출합니다.
컨테이너 내부에서 사용할 인증 파일을 준비합니다.

```bash
mkdir -p ~/hol/oci_genai_gateway/.oci
cp ~/hol/templates/oci_genai_gateway/.oci/config          ~/hol/oci_genai_gateway/.oci/config
cp ~/hol/templates/oci_genai_gateway/.oci/oci_api_key.pem ~/hol/oci_genai_gateway/.oci/oci_api_key.pem
chmod 600 ~/hol/oci_genai_gateway/.oci/config ~/hol/oci_genai_gateway/.oci/oci_api_key.pem
```

컨테이너 내부용 config:
```ini
[DEFAULT]
user=ocid1.user.oc1..aaaa...
fingerprint=ab:cd:ef:...:12
tenancy=ocid1.tenancy.oc1..aaaa...
region=us-chicago-1                  # GenAI 리전 (시카고, 호스트와 다름)
key_file=/root/.oci/oci_api_key.pem  # 컨테이너 내부 경로 (고정)
```

> **`key_file`이 `/root/.oci/`인 이유**
> Gateway 컨테이너는 `root` 사용자로 실행됩니다.
> 컨테이너 실행 시 `~/hol/oci_genai_gateway/.oci`를 `/root/.oci`로 마운트합니다.
>
> **region이 `us-chicago-1`인 이유**
> OCI GenAI 서비스는 시카고 리전에서만 제공됩니다.
> 호스트 config(춘천, IAM·ADW용)와 Gateway config(시카고, GenAI용)는 리전이 다릅니다.

---

### (부수) Step 5 · Gateway 소스 Clone

**왜 필요한가**: Gateway는 오픈소스 FastAPI 애플리케이션입니다.
소스를 받아야 Dockerfile로 이미지를 빌드할 수 있습니다.

```bash
git clone https://github.com/hiwylee/OCI_GenAI_access_gateway.git ~/hol/oci_genai_gateway

ls ~/hol/oci_genai_gateway/  # 확인
```

주요 파일:
```
oci_genai_gateway/
├── Dockerfile            # 이미지 빌드 정의
├── requirements.txt      # Python 패키지 목록
└── app/
    ├── app.py            # FastAPI 진입점
    ├── config.py         # 설정 (Step 6에서 생성)
    ├── models.yaml       # 지원 모델 목록
    └── api/              # 라우터, 스키마, 모델 구현
```

---

### (부수) Step 6 · Gateway config.py 생성

**왜 필요한가**: Gateway가 어느 리전의 GenAI API를 호출할지, 어떤 API Key를 쓸지 지정합니다.

```bash
envsubst < ~/hol/templates/oci_genai_gateway/app/config.py.template \
         > ~/hol/oci_genai_gateway/app/config.py

cat ~/hol/oci_genai_gateway/app/config.py  # 확인
```

생성되는 `config.py`:
```python
PORT = 8088
DEFAULT_API_KEYS = "ocigenerativeai"   # Bearer 토큰 (클라이언트가 이 값 사용)
API_ROUTE_PREFIX = "/v1"

AUTH_TYPE = "API_KEY"
REGION = "us-chicago-1"                         # HOL_REGION — GenAI 서비스 리전
OCI_COMPARTMENT = "ocid1.compartment.oc1..aaa"  # HOL_COMPARTMENT_OCID
```

---

### [실행] Step 10 · Gateway 컨테이너 빌드 + 기동

**이미지 빌드** (처음 한 번만, 약 3~5분):

```bash
podman network create hol-net 2>/dev/null || true  # Open-WebUI와 공유할 네트워크

podman build -t oci-genai-access-gateway:latest ~/hol/oci_genai_gateway
```

**컨테이너 실행**:

```bash
podman rm -f oci-genai-access-gateway 2>/dev/null || true
podman run -d \
  --name oci-genai-access-gateway \
  --network hol-net \
  -p 8088:8088 \
  -v ~/hol/oci_genai_gateway/.oci:/root/.oci:Z \
  --restart=always \
  localhost/oci-genai-access-gateway:latest
```

| 옵션 | 역할 |
|------|------|
| `--name oci-genai-access-gateway` | Open-WebUI가 이 이름으로 DNS 접근 |
| `--network hol-net` | Open-WebUI와 같은 네트워크 (컨테이너명 DNS 통신) |
| `-v .../oci:/root/.oci:Z` | Step 3에서 준비한 인증 파일 마운트 |
| `--restart=always` | VM 재시작 시 자동 기동 |

**검증**:
```bash
curl http://localhost:8088/health
# 예상: {"status":"OK"}

curl -s http://localhost:8088/v1/models \
     -H "Authorization: Bearer ocigenerativeai" | jq '.data[].id'
# 예상: 34개 이상 모델 ID 출력
```

---

## [핵심 2] Oracle ADW 연결 설정

**목표**: Open-WebUI가 Oracle Autonomous Database에 연결할 수 있도록 준비합니다.

ADW는 두 가지 역할을 동시에 수행합니다:
- **메타데이터 DB**: 사용자 계정, 채팅 기록, 모델 설정을 테이블에 저장
- **벡터 저장소**: 업로드한 문서를 임베딩 벡터로 저장하고, RAG 검색에 활용

ADW는 TLS 인증 기반 접속을 사용합니다. 비밀번호만으로는 접속할 수 없고,
강사가 배포한 **Wallet 파일**(인증서 묶음)이 있어야 합니다.

---

### (부수) Step 4 · Wallet 파일 준비

**왜 필요한가**: Wallet은 ADW 접속에 필요한 TLS 인증서 묶음입니다.
바이너리 파일은 강사가 `~/hol/wallet/`에 미리 배포해 두었습니다.
이 단계에서는 권한 설정과 접속 정보 텍스트 파일(tnsnames.ora, sqlnet.ora)만 생성합니다.

```bash
# 바이너리 파일 권한 설정
chmod 600 ~/hol/wallet/*.sso ~/hol/wallet/*.p12 ~/hol/wallet/*.pem 2>/dev/null || true

# 접속 정보 텍스트 파일 생성 (변수 치환)
envsubst < ~/hol/templates/wallet/tnsnames.ora.template > ~/hol/wallet/tnsnames.ora
envsubst < ~/hol/templates/wallet/sqlnet.ora.template   > ~/hol/wallet/sqlnet.ora
```

**검증**:
```bash
ls -la ~/hol/wallet/
cat ~/hol/wallet/sqlnet.ora
```

생성되는 `sqlnet.ora`:
```
WALLET_LOCATION = (SOURCE = (METHOD = file) (METHOD_DATA = (DIRECTORY="/home/opc/hol/wallet")))
SSL_SERVER_DN_MATCH=yes
```

생성되는 `tnsnames.ora` (일부):
```
holadw_medium = (description= (retry_count=20)(retry_delay=3)
  (address=(protocol=tcps)(port=1522)(host=adb.ap-chuncheon-1.oraclecloud.com))
  (connect_data=(service_name=g55136018110880_holadw_medium.adb.oraclecloud.com))
  (security=(ssl_server_dn_match=yes)))
```

> **바이너리 파일을 `envsubst`로 처리하면 안 되는 이유**
> `cwallet.sso`, `ewallet.p12` 등은 암호화된 바이너리 파일입니다.
> `envsubst`는 `$` 문자를 변수로 해석해 파일을 손상시킵니다.
> 텍스트 파일(`tnsnames.ora`, `sqlnet.ora`)만 치환 대상입니다.

---

## [핵심 3] Open-WebUI 채팅 UI 구축

**목표**: 브라우저에서 LLM과 대화하고, 문서를 업로드해 RAG 검색을 체험하는 웹 인터페이스를 배포합니다.

Open-WebUI는 Gateway(LLM 호출)와 ADW(데이터 저장)를 모두 사용합니다.
환경 변수 파일(`.env`)로 두 연결 정보를 주입한 뒤, 컨테이너를 실행합니다.

---

### (부수) Step 8 · Open-WebUI .env 생성

**왜 필요한가**: Open-WebUI 컨테이너가 시작될 때 어디에 있는 Gateway에 연결하고,
어느 DB 사용자로 ADW에 접속할지 알아야 합니다. `.env` 파일이 이 정보를 담습니다.

```bash
mkdir -p ~/hol/open-webui
envsubst < ~/hol/templates/openwebui/.env.template > ~/hol/open-webui/.env

cat ~/hol/open-webui/.env  # 확인
```

생성되는 `.env` 주요 항목:
```dotenv
# Gateway 연결 — 컨테이너명 DNS (hol-net 공유 네트워크)
OPENAI_API_BASE_URL=http://oci-genai-access-gateway:8088/v1
OPENAI_API_KEY=ocigenerativeai
RAG_OPENAI_API_BASE_URL=http://oci-genai-access-gateway:8088/v1
RAG_EMBEDDING_ENGINE=openai
RAG_EMBEDDING_MODEL=cohere.embed-v4.0

# 벡터 저장소
VECTOR_DB=oracle23ai

# Oracle DB — 메타데이터 (users, chats, models)
DATABASE_TYPE=oracle+oracledb
DATABASE_USER=hol_user01-meta         # HOL_USER + "-meta"
DATABASE_PASSWORD=WElCome123###

# Oracle DB — 벡터 저장소 (문서 임베딩)
ORACLE_DB_USER=hol_user01
ORACLE_DB_DSN=medium
ORACLE_WALLET_DIR=/home/opc/hol/wallet
ORACLE_VECTOR_LENGTH=1024             # cohere.embed-v4.0 차원 수
```

> **`OPENAI_API_BASE_URL`에 `localhost` 대신 컨테이너명을 쓰는 이유**
> `localhost:8088`은 Open-WebUI 컨테이너 자신을 가리킵니다.
> `hol-net` 같은 네트워크 안에서는 컨테이너명이 자동으로 DNS 이름으로 동작하므로,
> `oci-genai-access-gateway:8088`로 Gateway에 접근합니다.

---

### [실행] Step 11 · Open-WebUI 컨테이너 실행

**이미지 다운로드** (처음 한 번만, 약 2~3분):
```bash
podman pull ghcr.io/open-webui/open-webui:main
```

**컨테이너 실행**:
```bash
# podman rm -f open-webui 2>/dev/null || true
podman run -d \
  --name open-webui \
  --network hol-net \
  -p 8080:8080 \
  --env-file=/home/opc/hol/open-webui/.env \
  -v /home/opc/hol/wallet:/home/opc/hol/wallet:Z \
  -v open-webui:/app/backend/data \
  --restart=always \
  ghcr.io/open-webui/open-webui:main
```

| 옵션 | 역할 |
|------|------|
| `--network hol-net` | Gateway와 같은 네트워크 — 컨테이너명 DNS 통신 가능 |
| `--env-file=.env` | Step 8에서 생성한 Gateway·DB 연결 정보 주입 |
| `-v ~/hol/wallet:...:Z` | Step 4에서 준비한 Wallet 마운트 (`:Z` = SELinux 레이블) |
| `-v open-webui:/app/backend/data` | 채팅 기록·설정 영구 저장용 named volume |

**검증**:
```bash
podman logs open-webui 2>&1 | grep -E "started|error|database" | head -20
```

---

## 인프라 설정 — 외부 접근 + 서비스 지속성

### Step 9 · 방화벽 포트 오픈

```bash
sudo firewall-cmd --add-port=8088/tcp --add-port=8080/tcp --permanent
sudo firewall-cmd --reload

sudo firewall-cmd --list-ports  # 확인: 8080/tcp 8088/tcp
```

### Step 9 · 컨테이너 지속성 설정 (Linger)

```bash
sudo loginctl enable-linger opc

loginctl show-user opc | grep Linger  # 확인: Linger=yes
```

> rootless Podman은 기본적으로 SSH 세션이 살아있을 때만 컨테이너를 유지합니다.
> `loginctl enable-linger`를 설정하면 세션 종료(로그아웃) 후에도 컨테이너가 계속 실행됩니다.

---

## 최종 헬스체크

모든 구성 요소가 정상 동작하는지 확인합니다.

```bash
# 두 컨테이너 모두 Up 상태인지 확인
podman ps

# [핵심 1] Gateway 헬스체크
curl -s http://localhost:8088/health
# 예상: {"status":"OK"}

# [핵심 1] 사용 가능한 모델 목록
curl -s http://localhost:8088/v1/models \
     -H "Authorization: Bearer ocigenerativeai" | jq '.data[].id'

# [핵심 3] Open-WebUI 응답 확인
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
# 예상: 200
```

**브라우저 접속 URL**:
```bash
PUBLIC_IP=$(curl -sf --max-time 3 http://checkip.amazonaws.com 2>/dev/null \
            || hostname -I | awk '{print $1}')
echo "Open-WebUI : http://${PUBLIC_IP}:8080"
echo "Gateway    : http://${PUBLIC_IP}:8088/health"
```

---

## 문제 해결

### 컨테이너가 기동되지 않는 경우

```bash
podman logs oci-genai-access-gateway --tail 50
podman logs open-webui --tail 50
```

### Gateway OCI API 호출 실패

```bash
# 두 config 파일 비교 (region 등 불일치 확인)
diff ~/hol/.oci/config ~/hol/oci_genai_gateway/.oci/config

# 개인키 권한 확인
ls -la ~/hol/oci_genai_gateway/.oci/
```

### Open-WebUI DB 연결 실패

```bash
ls -la ~/hol/wallet/                             # Wallet 파일 확인
cat ~/hol/wallet/sqlnet.ora                       # DIRECTORY 경로 확인
grep "^${HOL_ADB_DSN}" ~/hol/wallet/tnsnames.ora  # DSN 확인
```

### 처음부터 다시 설정

```bash
podman rm -f open-webui oci-genai-access-gateway 2>/dev/null || true
podman rmi localhost/oci-genai-access-gateway:latest 2>/dev/null || true
podman volume rm open-webui 2>/dev/null || true
cd ~/hol && ./setup.sh
```

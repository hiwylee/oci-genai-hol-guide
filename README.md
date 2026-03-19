# OCI GenAI HOL — 수강생 가이드

이 저장소는 **OCI Generative AI Hands-on Lab** 수강생을 위한 가이드와 실습 접속 정보를 제공합니다.

## 실습 가이드 문서

| 문서 | 설명 |
|------|------|
| [HOL_README.md](./HOL_README.md) | 실습 개요 및 빠른 시작 가이드 |
| [HOL_prerequisites.md](./HOL_prerequisites.md) | 사전 학습 자료 (OCI, GenAI, ADW 개념) |
| [HOL_step_by_step.md](./HOL_step_by_step.md) | 단계별 상세 실습 가이드 |

## VM 접속 방법

강사에게 받은 VM IP 주소로 SSH 접속합니다.

### Mac / Linux

```bash
chmod 400 ssh-hol.key
ssh -i ssh-hol.key opc@<VM_IP>
```

### Windows (MobaXterm)

1. Session → SSH
2. Remote host: `<VM_IP>`, Username: `opc`
3. Advanced SSH settings → Use private key → `ssh-hol.key` 선택

### Windows (PuTTY)

1. `ssh-hol.key`를 PuTTYgen으로 `.ppk` 형식으로 변환
2. PuTTY → Host Name: `<VM_IP>`, Port: `22`
3. Connection → SSH → Auth → Private key file → `.ppk` 파일 선택

## SSH 키 사용 주의사항

> **중요**: 이 저장소에 포함된 `ssh-hol.key`는 **HOL 실습 전용 공용 임시 키**입니다.
>
> - 실습 종료 후 이 키는 폐기됩니다
> - 실제 운영 환경에 사용하지 마십시오
> - 개인 OCI 환경에 이 키를 등록하지 마십시오
> - 이 키를 타인에게 전달하지 마십시오 (HOL 수강생 전용)

## 강사 연락처

실습 중 문제가 발생하면 강사에게 문의하십시오.

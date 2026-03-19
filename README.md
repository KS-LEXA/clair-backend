# clair-backend

FastAPI + MySQL 기반 API 서버 저장소다.

## 책임 범위

- 계약서 업로드 API
- 분석 요청 및 결과 조회 API
- MySQL 저장 구조 관리
- OCR, LLM, 객체 탐지 결과 오케스트레이션

## 권장 구조

```text
app/
  api/
  core/
  schemas/
  services/
  parsers/
  rules/
  integrations/
  workers/
  tests/
```

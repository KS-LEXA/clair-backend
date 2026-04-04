# database

초기 MySQL 스키마는 [schema.sql](/Users/choseohyun/dev/clair-backend/database/schema.sql)에 둔다.

## 왜 여기 두는가

- 백엔드 저장소에서 DB 구조를 함께 관리하기 쉽다.
- 초기 MVP 단계에서 팀원이 바로 확인하고 실행하기 좋다.
- 이후 Alembic 또는 다른 마이그레이션 도구를 도입할 때 기준 스키마로 활용할 수 있다.

## 포함 테이블

- `users`
- `documents`
- `clauses`
- `extractions`
- `risk_flags`
- `vision_detections`
- `qa_logs`
- `analysis_jobs`

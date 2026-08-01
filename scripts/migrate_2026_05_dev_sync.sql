-- ─────────────────────────────────────────────────────────────────────────────
-- dev 브랜치 동기화 마이그레이션 (2026-05)
--
-- 대상: 예전 코드로 init_db()를 돌려 contracts/analysis_results/risk_clauses가
--       이미 만들어진 로컬 MySQL.
--
-- 왜 필요한가:
--   init_db()는 create_all()만 호출 — 기존 테이블의 컬럼/ENUM은 자동으로 안 바뀜.
--   dev에 머지된 모델 변경(분석 파이프라인 + 법령 준수 검사 + clause_id 매핑)이
--   기존 DB에 반영되지 않아 분석 시 "Unknown column" / "Data truncated" 에러 발생.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_05_dev_sync.sql
--
-- 멱등성:
--   ADD COLUMN은 INFORMATION_SCHEMA로 존재 여부 확인 후 실행 — 여러 번 돌려도 안전.
--   MODIFY COLUMN(ENUM 확장)은 같은 정의로 덮어쓰는 거라 자연히 멱등.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. contracts.status ENUM에 PENDING 추가 ─────────────────────────────────
ALTER TABLE contracts MODIFY COLUMN status
  ENUM('UPLOADED','PENDING','PROCESSING','COMPLETED','FAILED')
  NOT NULL DEFAULT 'UPLOADED';

-- ── 2. contracts.contract_type ENUM에 NDA/SERVICE/EMPLOYMENT 추가 ────────────
ALTER TABLE contracts MODIFY COLUMN contract_type
  ENUM('LABOR','COMPANY_RULE','FREELANCE','NDA','SERVICE','EMPLOYMENT','OTHER','UNKNOWN');

-- ── 3. analysis_results에 누락된 컬럼 추가 ─────────────────────────────────
-- raw_ocr_text: OCR 원문 (디버깅/재분석용)
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'analysis_results' AND COLUMN_NAME = 'raw_ocr_text');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE analysis_results ADD COLUMN raw_ocr_text TEXT NULL',
  'SELECT ''analysis_results.raw_ocr_text already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- analysis_duration_seconds: 분석 소요 시간 (성능 모니터링)
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'analysis_results' AND COLUMN_NAME = 'analysis_duration_seconds');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE analysis_results ADD COLUMN analysis_duration_seconds INT NULL',
  'SELECT ''analysis_results.analysis_duration_seconds already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 4. risk_clauses에 누락된 컬럼 추가 ─────────────────────────────────────
-- evidence_clause_ids: 위험 조항의 근거 clause_id 목록 (프론트 하이라이트용)
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'evidence_clause_ids');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN evidence_clause_ids JSON NULL',
  'SELECT ''risk_clauses.evidence_clause_ids already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- evidence_text: AI가 추출한 근거 원문 발췌
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'evidence_text');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN evidence_text TEXT NULL',
  'SELECT ''risk_clauses.evidence_text already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT '마이그레이션 완료' AS result;

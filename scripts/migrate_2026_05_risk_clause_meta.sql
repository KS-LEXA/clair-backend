-- ─────────────────────────────────────────────────────────────────────────────
-- risk_clauses 메타데이터 컬럼 추가 (2026-05)
--
-- 추가 내역:
--   title             VARCHAR(200) NULL  — 사용자 친화적 위험 조항명 (한국어)
--   severity_score    INT NULL DEFAULT 5 — 1~10 심각도 수치
--   confidence        FLOAT NULL          — 0.0~1.0 AI 신뢰도
--   problematic_text  TEXT NULL          — 위험 판단 근거가 된 계약서 원문
--
-- 왜:
--   clair-ai 위험 조항 분석이 고도화되어 차등 점수·신뢰도·제목·원문을 함께 반환.
--   안전 점수 계산(app/services/scoring.py)에서 severity_score와 confidence를
--   가중치로 사용. 모델(ORM)에는 컬럼 정의되어 있으나 DB에 적용 누락.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_05_risk_clause_meta.sql
--
-- 멱등성:
--   ADD COLUMN은 INFORMATION_SCHEMA로 존재 확인 후 실행 — 여러 번 돌려도 안전.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. title 추가 ──────────────────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'title');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN title VARCHAR(200) NULL',
  'SELECT ''risk_clauses.title already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 2. severity_score 추가 ─────────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'severity_score');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN severity_score INT NULL DEFAULT 5',
  'SELECT ''risk_clauses.severity_score already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 3. confidence 추가 ─────────────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'confidence');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN confidence FLOAT NULL',
  'SELECT ''risk_clauses.confidence already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 4. problematic_text 추가 ───────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'risk_clauses' AND COLUMN_NAME = 'problematic_text');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE risk_clauses ADD COLUMN problematic_text TEXT NULL',
  'SELECT ''risk_clauses.problematic_text already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'risk_clauses 메타데이터 마이그레이션 완료' AS result;

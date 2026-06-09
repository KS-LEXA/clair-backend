-- ─────────────────────────────────────────────────────────────────────────────
-- contracts 테이블에 analysis_requested_at 컬럼 추가 (2026-06)
--
-- 추가 내역:
--   analysis_requested_at DATETIME NULL  — 분석(재분석 포함) 요청 시각
--
-- 왜:
--   기존 계약서 재분석 시, 이전 분석의 completed 상태/시각이 status·detail 응답에
--   계속 내려가 프론트가 옛 결과를 새 결과로 오인하는 문제가 있었다. 분석 요청마다
--   이 시각을 갱신하고 시작/완료 시각을 리셋하여, "이번 요청 이후 완료된 결과"만
--   신뢰하도록 신선도 기준을 제공한다. job_id는 (contract_id + 이 시각)으로 파생.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_06_contract_analysis_requested_at.sql
--
-- 멱등성:
--   ADD COLUMN은 INFORMATION_SCHEMA로 존재 확인 후 실행 — 여러 번 돌려도 안전.
-- ─────────────────────────────────────────────────────────────────────────────

SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contracts' AND COLUMN_NAME = 'analysis_requested_at');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE contracts ADD COLUMN analysis_requested_at DATETIME NULL',
  'SELECT ''contracts.analysis_requested_at already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'contracts.analysis_requested_at 마이그레이션 완료' AS result;

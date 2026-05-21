-- ─────────────────────────────────────────────────────────────────────────────
-- users 테이블에 profile_image_path 컬럼 추가 (2026-05)
--
-- 추가 내역:
--   profile_image_path VARCHAR(500) NULL  — 프로필 이미지 상대 경로
--
-- 왜:
--   마이페이지에서 프로필 이미지 업로드/표시가 필요. 절대 URL은 매번 응답 시점에
--   backend_base_url과 조합해 만들기 때문에 DB에는 파일 시스템 상대 경로만 저장.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_05_user_profile_image.sql
--
-- 멱등성:
--   ADD COLUMN은 INFORMATION_SCHEMA로 존재 확인 후 실행 — 여러 번 돌려도 안전.
-- ─────────────────────────────────────────────────────────────────────────────

SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'profile_image_path');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN profile_image_path VARCHAR(500) NULL',
  'SELECT ''users.profile_image_path already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'users.profile_image_path 마이그레이션 완료' AS result;

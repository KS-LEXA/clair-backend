-- ─────────────────────────────────────────────────────────────────────────────
-- 회원가입 이메일 인증 (2026-05)
--
-- 추가 내역:
--   1) email_verifications 테이블 신설 — 가입 전 단계의 6자리 코드 인증
--      · email          VARCHAR(255) NOT NULL  — 인증 대상 이메일
--      · code_hash      VARCHAR(64)  NOT NULL  — 6자리 코드의 SHA-256 해시
--      · expires_at     DATETIME     NOT NULL  — 코드 만료 시각 (요청 후 10분)
--      · attempt_count  INT          NOT NULL DEFAULT 0  — confirm 실패 누적 (5회 시 무효)
--      · verified_at    DATETIME     NULL      — 인증 완료 시각
--      · created_at     DATETIME              DEFAULT CURRENT_TIMESTAMP
--      · UNIQUE INDEX(email) — 이메일당 활성 인증 레코드 1개 보장 (재요청 시 UPSERT)
--
--   2) users.email_verified_at DATETIME NULL — 가입 시점에 채워짐 (소셜 유저는 IdP 신뢰로 자동 채움)
--
-- 왜:
--   가입 전 코드 인증 흐름 — 미인증 유저가 DB에 남지 않도록 회원가입 전에 별도 검증 단계.
--   소셜 로그인은 IdP가 이메일 소유권을 검증한 뒤 넘겨주므로 추가 단계 없이 verified 처리.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_05_email_verification.sql
--
-- 멱등성:
--   테이블/컬럼은 INFORMATION_SCHEMA로 존재 확인 후 실행 — 여러 번 돌려도 안전.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. email_verifications 테이블 ──────────────────────────────────────────
SET @tbl_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'email_verifications');
SET @sql := IF(@tbl_exists = 0,
  'CREATE TABLE email_verifications (
     id            INT          NOT NULL AUTO_INCREMENT,
     email         VARCHAR(255) NOT NULL,
     code_hash     VARCHAR(64)  NOT NULL,
     expires_at    DATETIME     NOT NULL,
     attempt_count INT          NOT NULL DEFAULT 0,
     verified_at   DATETIME     NULL,
     created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
     PRIMARY KEY (id),
     UNIQUE KEY uq_email_verifications_email (email)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4',
  'SELECT ''email_verifications already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 2. users.email_verified_at ─────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'email_verified_at');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL',
  'SELECT ''users.email_verified_at already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'email_verifications + users.email_verified_at 마이그레이션 완료' AS result;

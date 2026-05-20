-- ─────────────────────────────────────────────────────────────────────────────
-- chat_sessions 메타데이터 컬럼 추가 (2026-05)
--
-- 추가 내역:
--   total_message_count INT NOT NULL DEFAULT 0  — 세션의 메시지 총 개수
--   last_message_at     DATETIME NULL           — 마지막 메시지 시각
--
-- 왜:
--   세션 목록 화면에서 "메시지 N개 / 마지막 대화 N분 전" 같은 정보를 보여줘야 하는데,
--   매번 chat_messages를 COUNT/MAX 하면 세션 수가 늘수록 느려진다. 컬럼으로 캐싱.
--
-- 실행:
--   mysql -u root -p clair_db < scripts/migrate_2026_05_chat_session_meta.sql
--
-- 멱등성:
--   ADD COLUMN은 INFORMATION_SCHEMA로 존재 확인 후 실행 — 여러 번 돌려도 안전.
--   백필 UPDATE도 멱등 (chat_messages 현재 상태 기준으로 다시 채움).
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. total_message_count 추가 ─────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'chat_sessions' AND COLUMN_NAME = 'total_message_count');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE chat_sessions ADD COLUMN total_message_count INT NOT NULL DEFAULT 0',
  'SELECT ''chat_sessions.total_message_count already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 2. last_message_at 추가 ────────────────────────────────────────────────
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'chat_sessions' AND COLUMN_NAME = 'last_message_at');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE chat_sessions ADD COLUMN last_message_at DATETIME NULL',
  'SELECT ''chat_sessions.last_message_at already exists'' AS skip_reason');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── 3. 기존 세션 백필 ──────────────────────────────────────────────────────
-- 모든 세션의 카운터/시각을 chat_messages 기준으로 다시 계산 — 멱등.
UPDATE chat_sessions s
LEFT JOIN (
  SELECT session_id, COUNT(*) AS cnt, MAX(created_at) AS last_at
  FROM chat_messages
  GROUP BY session_id
) m ON m.session_id = s.id
SET
  s.total_message_count = COALESCE(m.cnt, 0),
  s.last_message_at     = m.last_at;

SELECT 'chat_sessions 메타데이터 마이그레이션 완료' AS result;

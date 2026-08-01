CREATE DATABASE IF NOT EXISTS clair
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE clair;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  name VARCHAR(100) NULL,
  role VARCHAR(50) NOT NULL DEFAULT 'user',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS documents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(255) NOT NULL,
  contract_type VARCHAR(100) NULL,
  source_file_path VARCHAR(500) NOT NULL,
  source_file_name VARCHAR(255) NULL,
  source_file_mime VARCHAR(100) NULL,
  source_file_size BIGINT UNSIGNED NULL,
  language_code VARCHAR(20) NOT NULL DEFAULT 'ko',
  status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
  summary TEXT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_documents_user_id (user_id),
  KEY idx_documents_contract_type (contract_type),
  KEY idx_documents_status (status),
  CONSTRAINT fk_documents_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS clauses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  clause_number VARCHAR(50) NULL,
  clause_title VARCHAR(255) NULL,
  clause_text LONGTEXT NOT NULL,
  page_no INT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_clauses_document_id (document_id),
  KEY idx_clauses_sort_order (document_id, sort_order),
  CONSTRAINT fk_clauses_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS extractions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  counterparty_a VARCHAR(255) NULL,
  counterparty_b VARCHAR(255) NULL,
  signing_date DATE NULL,
  start_date DATE NULL,
  end_date DATE NULL,
  amount_text VARCHAR(255) NULL,
  amount_value DECIMAL(18,2) NULL,
  currency VARCHAR(20) NULL,
  has_termination_clause BOOLEAN NOT NULL DEFAULT FALSE,
  has_liability_clause BOOLEAN NOT NULL DEFAULT FALSE,
  has_confidentiality_clause BOOLEAN NOT NULL DEFAULT FALSE,
  has_dispute_clause BOOLEAN NOT NULL DEFAULT FALSE,
  has_auto_renewal_clause BOOLEAN NOT NULL DEFAULT FALSE,
  confidence_score DECIMAL(5,2) NULL,
  raw_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_extractions_document_id (document_id),
  CONSTRAINT fk_extractions_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS risk_flags (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  clause_id BIGINT UNSIGNED NULL,
  risk_type VARCHAR(100) NOT NULL,
  severity VARCHAR(20) NOT NULL DEFAULT 'medium',
  reason TEXT NOT NULL,
  evidence_text TEXT NULL,
  suggested_checkpoint TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_risk_flags_document_id (document_id),
  KEY idx_risk_flags_clause_id (clause_id),
  KEY idx_risk_flags_risk_type (risk_type),
  CONSTRAINT fk_risk_flags_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_risk_flags_clause
    FOREIGN KEY (clause_id) REFERENCES clauses(id)
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS vision_detections (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  page_no INT NULL,
  detection_type VARCHAR(50) NOT NULL DEFAULT 'object',
  label VARCHAR(100) NOT NULL,
  confidence DECIMAL(5,2) NOT NULL,
  bbox_json JSON NOT NULL,
  image_path VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_vision_detections_document_id (document_id),
  KEY idx_vision_detections_label (label),
  CONSTRAINT fk_vision_detections_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS qa_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  question TEXT NOT NULL,
  answer LONGTEXT NULL,
  evidence_clause_ids JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_qa_logs_document_id (document_id),
  CONSTRAINT fk_qa_logs_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis_jobs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  document_id BIGINT UNSIGNED NOT NULL,
  job_type VARCHAR(50) NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'queued',
  started_at TIMESTAMP NULL,
  finished_at TIMESTAMP NULL,
  error_message TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_analysis_jobs_document_id (document_id),
  KEY idx_analysis_jobs_status (status),
  CONSTRAINT fk_analysis_jobs_document
    FOREIGN KEY (document_id) REFERENCES documents(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

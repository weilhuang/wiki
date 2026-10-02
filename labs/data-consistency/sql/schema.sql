-- v1: only the fresh, run-owned consistency_lab database may receive this schema.
CREATE TABLE inventory (
  sku VARCHAR(40) PRIMARY KEY,
  initial_qty INT NOT NULL,
  available INT NOT NULL,
  version BIGINT NOT NULL DEFAULT 0,
  CONSTRAINT ck_available CHECK (available >= 0)
) ENGINE=InnoDB;
CREATE TABLE orders (
  order_id VARCHAR(100) PRIMARY KEY,
  scope VARCHAR(60) NOT NULL,
  business_id VARCHAR(80) NOT NULL,
  sku VARCHAR(40) NOT NULL,
  quantity INT NOT NULL,
  state VARCHAR(20) NOT NULL,
  version BIGINT NOT NULL,
  UNIQUE KEY uk_business (scope, business_id),
  CONSTRAINT ck_quantity CHECK (quantity > 0),
  FOREIGN KEY (sku) REFERENCES inventory(sku)
) ENGINE=InnoDB;
CREATE TABLE operations (
  scope VARCHAR(60) NOT NULL,
  idem_key VARCHAR(80) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  status VARCHAR(20) NOT NULL,
  order_id VARCHAR(100),
  response_json JSON,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (scope, idem_key)
) ENGINE=InnoDB;
CREATE TABLE outbox (
  event_id VARCHAR(120) PRIMARY KEY,
  order_id VARCHAR(100) NOT NULL,
  aggregate_version BIGINT NOT NULL,
  schema_version INT NOT NULL,
  payload JSON NOT NULL,
  sent TINYINT NOT NULL DEFAULT 0,
  attempts INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_order_version (order_id, aggregate_version),
  KEY ix_relay (sent, created_at, event_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id)
) ENGINE=InnoDB;
-- Controlled durable delivery receiver, NOT a real broker. Each accept commits
-- on a separate connection; duplicates deliberately remain visible.
CREATE TABLE delivery_receipts (
  receipt_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_id VARCHAR(120) NOT NULL,
  payload JSON NOT NULL,
  accepted_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;
CREATE TABLE consumer_dedup (
  consumer_name VARCHAR(40) NOT NULL,
  event_id VARCHAR(120) NOT NULL,
  PRIMARY KEY (consumer_name, event_id)
) ENGINE=InnoDB;
CREATE TABLE order_projection (
  order_id VARCHAR(100) PRIMARY KEY,
  quantity INT NOT NULL,
  state VARCHAR(20) NOT NULL,
  version BIGINT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE effect_log (
  effect_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_id VARCHAR(120) NOT NULL,
  order_id VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

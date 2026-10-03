CREATE TABLE IF NOT EXISTS orders (
  order_id INT NOT NULL PRIMARY KEY,
  tenant_id INT NOT NULL,
  state TINYINT NOT NULL,
  created_at INT NOT NULL,
  amount INT NOT NULL,
  note VARCHAR(64) NOT NULL,
  KEY idx_tenant_state_created (tenant_id, state, created_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS inventory (
  sku INT NOT NULL PRIMARY KEY,
  available INT NOT NULL,
  CONSTRAINT available_nonnegative CHECK (available >= 0)
) ENGINE=InnoDB;

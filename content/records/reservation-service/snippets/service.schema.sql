CREATE TABLE products (
 sku VARCHAR(48) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 stock BIGINT NOT NULL,
 CONSTRAINT product_stock_nonnegative CHECK (stock >= 0)
) ENGINE=InnoDB;
CREATE TABLE operations (
 subject VARCHAR(48) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 operation_id VARCHAR(48) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 sku VARCHAR(48) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 quantity BIGINT NOT NULL,
 state ENUM('pending','confirmed','rejected') NOT NULL,
 PRIMARY KEY(subject, operation_id),
 CONSTRAINT operation_quantity_positive CHECK (quantity BETWEEN 1 AND 100)
) ENGINE=InnoDB;

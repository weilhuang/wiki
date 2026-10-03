UPDATE inventory
SET available = available - 2
WHERE sku = 1 AND available >= 2;
SELECT ROW_COUNT();

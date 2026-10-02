-- Each query returns violations. Zero rows is the expected healthy result.
SELECT i.sku, i.initial_qty, i.available,
       COALESCE(SUM(CASE WHEN o.state='reserved' THEN o.quantity ELSE 0 END),0) AS reserved
FROM inventory i LEFT JOIN orders o ON o.sku=i.sku
GROUP BY i.sku,i.initial_qty,i.available
HAVING i.available < 0 OR i.initial_qty <> i.available + reserved;
SELECT o.order_id FROM orders o LEFT JOIN outbox x
  ON x.order_id=o.order_id AND x.aggregate_version=o.version
WHERE x.event_id IS NULL;
SELECT event_id, COUNT(*) AS effects FROM effect_log
GROUP BY event_id HAVING COUNT(*)>1;
SELECT x.event_id FROM outbox x LEFT JOIN consumer_dedup d
  ON d.event_id=x.event_id AND d.consumer_name='orders-v1'
WHERE d.event_id IS NULL;
SELECT o.order_id,o.version,p.version AS projected_version FROM orders o
LEFT JOIN order_projection p ON p.order_id=o.order_id
WHERE p.order_id IS NULL OR p.version<>o.version
   OR p.quantity<>o.quantity OR p.state<>o.state;

SELECT order_id, created_at
FROM orders
WHERE tenant_id = 1 AND state = 1 AND created_at >= 3
ORDER BY created_at, order_id;

SELECT order_id, created_at
FROM orders FORCE INDEX (idx_tenant_state_created)
WHERE tenant_id = 1 AND state = 1 AND created_at >= 3
ORDER BY created_at, order_id;

SELECT order_id, created_at, note
FROM orders FORCE INDEX (idx_tenant_state_created)
WHERE tenant_id = 1 AND state = 1 AND created_at >= 3
ORDER BY created_at, order_id;

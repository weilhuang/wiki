	_, err = tx.ExecContext(ctx, "INSERT INTO operations (subject, operation_id, sku, quantity, state) VALUES (?, ?, ?, ?, 'pending')", subject, in.OperationID, in.SKU, in.Quantity)
	if duplicate(err) {
		if rollbackErr := tx.Rollback(); rollbackErr != nil && !errors.Is(rollbackErr, sql.ErrTxDone) {
			return op, rollbackErr
		}
		op, err = s.Get(ctx, subject, in.OperationID)
		if err != nil {
			return op, err
		}
		return replay(op, in)
	}
	if err != nil {
		return op, err
	}

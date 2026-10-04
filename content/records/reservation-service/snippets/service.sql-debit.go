	result, err := tx.ExecContext(ctx, "UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?", in.Quantity, in.SKU, in.Quantity)
	if err != nil {
		return op, err
	}
	affected, err := result.RowsAffected()
	if err != nil {
		return op, err
	}
	state, err := finalState(affected)
	if err != nil {
		return op, err
	}

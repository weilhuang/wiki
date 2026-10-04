	result = tx.Exec("UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?", in.Quantity, in.SKU, in.Quantity)
	if result.Error != nil {
		return op, result.Error
	}
	state, err := finalState(result.RowsAffected)
	if err != nil {
		return op, err
	}

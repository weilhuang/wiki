func (s *SQL) List(ctx context.Context, subject string, limit int) ([]domain.Operation, error) {
	rows, err := s.DB.QueryContext(ctx, "SELECT operation_id, sku, quantity, state FROM operations WHERE subject = ? ORDER BY operation_id LIMIT ?", subject, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]domain.Operation, 0, limit)
	for rows.Next() {
		var op domain.Operation
		if err = rows.Scan(&op.OperationID, &op.SKU, &op.Quantity, &op.State); err != nil {
			return nil, err
		}
		out = append(out, op)
	}
	if err = rows.Err(); err != nil {
		return nil, err
	}
	if err = rows.Close(); err != nil {
		return nil, err
	}
	return out, nil
}

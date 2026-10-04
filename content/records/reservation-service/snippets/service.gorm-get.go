func (s *GORM) Get(ctx context.Context, subject, id string) (domain.Operation, error) {
	var row operationRow
	result := s.DB.WithContext(ctx).Where("subject = ? AND operation_id = ?", subject, id).Take(&row)
	if errors.Is(result.Error, gorm.ErrRecordNotFound) {
		return domain.Operation{}, domain.Fail(domain.NotFound, nil)
	}
	if result.Error != nil {
		return domain.Operation{}, result.Error
	}
	return domain.Operation{OperationID: row.OperationID, SKU: row.SKU, Quantity: row.Quantity, State: row.State}, nil
}

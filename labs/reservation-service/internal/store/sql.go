package store

import (
	"context"
	"database/sql"
	"errors"

	"example.com/reservation-service/internal/domain"
)

type SQL struct {
	DB    *sql.DB
	Hooks Hooks
}

func (s *SQL) Reserve(ctx context.Context, subject string, in domain.Input) (op domain.Operation, err error) {
	tx, err := s.DB.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return op, err
	}
	defer tx.Rollback()
	var connectionID int64
	if s.Hooks != nil {
		if err = tx.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&connectionID); err != nil {
			return op, err
		}
	}
	if err = step(s.Hooks, ctx, "begin", connectionID); err != nil {
		return op, err
	}
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
	// Validate the product after the unique claim; missing products roll back the claim.
	var exists string
	if err = tx.QueryRowContext(ctx, "SELECT sku FROM products WHERE sku = ?", in.SKU).Scan(&exists); err != nil {
		return op, missing(err)
	}
	if err = step(s.Hooks, ctx, "claimed", connectionID); err != nil {
		return op, err
	}
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
	if err = step(s.Hooks, ctx, "debited", connectionID); err != nil {
		return op, err
	}
	result, err = tx.ExecContext(ctx, "UPDATE operations SET state = ? WHERE subject = ? AND operation_id = ?", state, subject, in.OperationID)
	if err != nil {
		return op, err
	}
	n, err := result.RowsAffected()
	if err != nil {
		return op, err
	}
	if n != 1 {
		return op, errors.New("operation finalization row count")
	}
	if err = step(s.Hooks, ctx, "before_commit", connectionID); err != nil {
		return op, err
	}
	if err = tx.Commit(); err != nil {
		return op, domain.Fail(domain.OutcomeUnknown, err)
	}
	return domain.Operation{OperationID: in.OperationID, SKU: in.SKU, Quantity: in.Quantity, State: state}, nil
}
func (s *SQL) Get(ctx context.Context, subject, id string) (op domain.Operation, err error) {
	err = s.DB.QueryRowContext(ctx, "SELECT operation_id, sku, quantity, state FROM operations WHERE subject = ? AND operation_id = ?", subject, id).Scan(&op.OperationID, &op.SKU, &op.Quantity, &op.State)
	return op, missing(err)
}
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

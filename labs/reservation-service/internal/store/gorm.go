package store

import (
	"context"
	"database/sql"
	"errors"

	"example.com/reservation-service/internal/domain"
	gm "gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type GORM struct {
	DB    *gorm.DB
	Pool  *sql.DB
	Hooks Hooks
}

func NewGORM(pool *sql.DB, h Hooks) (*GORM, error) {
	db, err := gorm.Open(gm.New(gm.Config{Conn: pool, SkipInitializeWithVersion: true}), &gorm.Config{SkipDefaultTransaction: true, Logger: logger.Default.LogMode(logger.Silent), DisableAutomaticPing: true})
	if err != nil {
		return nil, err
	}
	return &GORM{DB: db, Pool: pool, Hooks: h}, nil
}
func (s *GORM) Reserve(ctx context.Context, subject string, in domain.Input) (op domain.Operation, err error) {
	tx := s.DB.WithContext(ctx).Begin(&sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if tx.Error != nil {
		return op, tx.Error
	}
	defer tx.Rollback()
	var connectionID int64
	if s.Hooks != nil {
		if err = tx.Raw("SELECT CONNECTION_ID()").Row().Scan(&connectionID); err != nil {
			return op, err
		}
	}
	if err = step(s.Hooks, ctx, "begin", connectionID); err != nil {
		return op, err
	}
	result := tx.Exec("INSERT INTO operations (subject, operation_id, sku, quantity, state) VALUES (?, ?, ?, ?, 'pending')", subject, in.OperationID, in.SKU, in.Quantity)
	if duplicate(result.Error) {
		if e := tx.Rollback().Error; e != nil && !errors.Is(e, sql.ErrTxDone) {
			return op, e
		}
		op, err = s.Get(ctx, subject, in.OperationID)
		if err != nil {
			return op, err
		}
		return replay(op, in)
	}
	if result.Error != nil {
		return op, result.Error
	}
	var exists string
	if err = tx.Raw("SELECT sku FROM products WHERE sku = ?", in.SKU).Row().Scan(&exists); err != nil {
		return op, missing(err)
	}
	if err = step(s.Hooks, ctx, "claimed", connectionID); err != nil {
		return op, err
	}
	result = tx.Exec("UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?", in.Quantity, in.SKU, in.Quantity)
	if result.Error != nil {
		return op, result.Error
	}
	state, err := finalState(result.RowsAffected)
	if err != nil {
		return op, err
	}
	if err = step(s.Hooks, ctx, "debited", connectionID); err != nil {
		return op, err
	}
	result = tx.Exec("UPDATE operations SET state = ? WHERE subject = ? AND operation_id = ?", state, subject, in.OperationID)
	if result.Error != nil {
		return op, result.Error
	}
	if result.RowsAffected != 1 {
		return op, errors.New("operation finalization row count")
	}
	if err = step(s.Hooks, ctx, "before_commit", connectionID); err != nil {
		return op, err
	}
	if err = tx.Commit().Error; err != nil {
		return op, domain.Fail(domain.OutcomeUnknown, err)
	}
	return domain.Operation{OperationID: in.OperationID, SKU: in.SKU, Quantity: in.Quantity, State: state}, nil
}

type operationRow struct {
	Subject     string `gorm:"column:subject;primaryKey"`
	OperationID string `gorm:"column:operation_id;primaryKey"`
	SKU         string `gorm:"column:sku"`
	Quantity    int64  `gorm:"column:quantity"`
	State       string `gorm:"column:state"`
}

func (operationRow) TableName() string { return "operations" }
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
func (s *GORM) List(ctx context.Context, subject string, limit int) ([]domain.Operation, error) {
	rows, err := s.DB.WithContext(ctx).Model(&operationRow{}).Select("operation_id", "sku", "quantity", "state").Where("subject = ?", subject).Order("operation_id").Limit(limit).Rows()
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

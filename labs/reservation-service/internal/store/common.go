package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"example.com/reservation-service/internal/domain"
	mysql "github.com/go-sql-driver/mysql"
)

// Hooks creates deterministic test interleavings; production passes nil.
// The connection ID is zero when no transaction exists.
type Hooks func(context.Context, string, int64) error

func step(h Hooks, ctx context.Context, name string, id int64) error {
	if h == nil {
		return nil
	}
	return h(ctx, name, id)
}
func duplicate(err error) bool {
	var e *mysql.MySQLError
	return errors.As(err, &e) && e.Number == 1062
}
func missing(err error) error {
	if errors.Is(err, sql.ErrNoRows) {
		return domain.Fail(domain.NotFound, nil)
	}
	return err
}
func replay(op domain.Operation, in domain.Input) (domain.Operation, error) {
	if !op.Same(in) {
		return domain.Operation{}, domain.Fail(domain.Conflict, nil)
	}
	return op, nil
}
func Open(dsn string) (*sql.DB, error) {
	cfg, err := mysql.ParseDSN(dsn)
	if err != nil {
		return nil, errors.New("invalid database configuration")
	}
	cfg.MultiStatements = false
	cfg.Timeout = 2 * time.Second
	cfg.ReadTimeout = 3 * time.Second
	cfg.WriteTimeout = 3 * time.Second
	connector, err := mysql.NewConnector(cfg)
	if err != nil {
		return nil, errors.New("invalid database configuration")
	}
	db := sql.OpenDB(connector)
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(4)
	db.SetConnMaxIdleTime(time.Minute)
	return db, nil
}
func finalState(rows int64) (string, error) {
	if rows == 0 {
		return "rejected", nil
	}
	if rows == 1 {
		return "confirmed", nil
	}
	return "", fmt.Errorf("unexpected affected row count: %d", rows)
}

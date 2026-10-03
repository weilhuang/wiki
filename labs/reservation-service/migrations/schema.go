package migrations

import (
	"context"
	"database/sql"
	_ "embed"
	"strings"
)

//go:embed 001_init.sql
var schema string

// Apply is an explicit one-time migration for a fresh teaching schema.
// Reapplying fails instead of silently accepting a different table definition.
func Apply(ctx context.Context, db *sql.DB) error {
	for _, statement := range strings.Split(schema, ";") {
		if strings.TrimSpace(statement) == "" {
			continue
		}
		if _, err := db.ExecContext(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

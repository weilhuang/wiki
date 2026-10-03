//go:build integration

package tests

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"runtime"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"example.com/reservation-service/internal/domain"
	"example.com/reservation-service/internal/store"
	"example.com/reservation-service/migrations"
	mysql "github.com/go-sql-driver/mysql"
)

type fixture struct {
	t                   *testing.T
	backend             string
	db, observer, admin *sql.DB
	repo                domain.Repository
	service             *domain.Service
	schema, dsn         string
}

func newFixture(t *testing.T, backend string, stock int64) *fixture {
	t.Helper()
	if runtime.Version() != "go1.27.1" {
		t.Fatalf("VERSION: got %s", runtime.Version())
	}
	raw := os.Getenv("RESERVATION_MYSQL_ADMIN_DSN")
	if raw == "" {
		t.Fatal("REQUIRED_ENV: RESERVATION_MYSQL_ADMIN_DSN; real MySQL tests cannot skip")
	}
	cfg, err := mysql.ParseDSN(raw)
	must(t, err, "admin configuration")
	cfg.DBName = ""
	admin, err := store.Open(cfg.FormatDSN())
	must(t, err, "admin open")
	t.Cleanup(func() { must(t, admin.Close(), "admin close") })
	var version string
	must(t, admin.QueryRow("SELECT VERSION()").Scan(&version), "version")
	if version != "8.4.7" {
		t.Fatalf("MYSQL_VERSION: got %q", version)
	}
	var salt [6]byte
	_, err = rand.Read(salt[:])
	must(t, err, "random schema")
	schema := "reservation_" + backend + "_" + hex.EncodeToString(salt[:])
	_, err = admin.Exec("CREATE DATABASE " + schema)
	must(t, err, "create owned schema")
	t.Cleanup(func() { _, e := admin.Exec("DROP DATABASE " + schema); must(t, e, "drop owned schema") })
	cfg.DBName = schema
	dsn := cfg.FormatDSN()
	db, err := store.Open(dsn)
	must(t, err, "store open")
	observer, err := store.Open(dsn)
	must(t, err, "observer open")
	t.Cleanup(func() { must(t, db.Close(), "store close"); must(t, observer.Close(), "observer close") })
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	must(t, migrations.Apply(ctx, db), "migration")
	_, err = observer.Exec("INSERT INTO products(sku, stock) VALUES ('book', ?)", stock)
	must(t, err, "seed")
	f := &fixture{t: t, backend: backend, db: db, observer: observer, admin: admin, schema: schema, dsn: dsn}
	f.setHooks(nil)
	t.Logf("FIXTURE mysql=%s backend=%s", version, backend)
	return f
}
func (f *fixture) setHooks(h store.Hooks) {
	switch f.backend {
	case "sql":
		f.repo = &store.SQL{DB: f.db, Hooks: h}
	case "gorm":
		s, err := store.NewGORM(f.db, h)
		must(f.t, err, "gorm open")
		f.repo = s
	default:
		f.t.Fatal("unknown backend")
	}
	f.service = &domain.Service{Repo: f.repo}
}
func must(t *testing.T, err error, label string) {
	t.Helper()
	if err != nil {
		t.Fatalf("%s failed (%T)", label, err)
	}
}
func equal[T comparable](t *testing.T, got, want T, marker string) {
	t.Helper()
	if got != want {
		semanticFailure(t, marker, fmt.Sprintf("%#v", got), fmt.Sprintf("%#v", want))
	}
}
func (f *fixture) facts(stock int64, count int) {
	f.t.Helper()
	var got int64
	must(f.t, f.observer.QueryRow("SELECT stock FROM products WHERE sku='book'").Scan(&got), "observe stock")
	equal(f.t, got, stock, "PERSISTED_STOCK")
	var n int
	must(f.t, f.observer.QueryRow("SELECT COUNT(*) FROM operations").Scan(&n), "observe operations")
	equal(f.t, n, count, "PERSISTED_OPERATIONS")
	must(f.t, f.observer.QueryRow("SELECT COUNT(*) FROM operations WHERE state='pending'").Scan(&n), "observe pending")
	equal(f.t, n, 0, "NO_COMMITTED_PENDING")
}
func (f *fixture) observe(id, subject, state string, quantity int64) {
	f.t.Helper()
	var gotState, sku string
	var qty int64
	must(f.t, f.observer.QueryRow("SELECT sku,quantity,state FROM operations WHERE subject=? AND operation_id=?", subject, id).Scan(&sku, &qty, &gotState), "observe operation")
	equal(f.t, sku, "book", "PERSISTED_SKU")
	equal(f.t, qty, quantity, "PERSISTED_QUANTITY")
	equal(f.t, gotState, state, "PERSISTED_STATE")
}
func (f *fixture) poolReturned() {
	f.t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	waitFor(f.t, ctx, func() bool { return f.db.Stats().InUse == 0 }, "POOL_RETURN")
	must(f.t, f.db.PingContext(ctx), "pool usable")
}
func waitFor(t *testing.T, ctx context.Context, condition func() bool, marker string) {
	t.Helper()
	ticker := time.NewTicker(5 * time.Millisecond)
	defer ticker.Stop()
	for {
		if condition() {
			return
		}
		select {
		case <-ctx.Done():
			t.Fatalf("%s: observation deadline", marker)
		case <-ticker.C:
		}
	}
}
func (f *fixture) lockProduct() (*sql.Tx, func()) {
	f.t.Helper()
	tx, err := f.observer.BeginTx(context.Background(), nil)
	must(f.t, err, "lock begin")
	var v int64
	must(f.t, tx.QueryRow("SELECT stock FROM products WHERE sku='book' FOR UPDATE").Scan(&v), "lock product")
	release := func() {
		err := tx.Rollback()
		if err != nil && !errors.Is(err, sql.ErrTxDone) {
			f.t.Fatal("lock rollback failed")
		}
	}
	f.t.Cleanup(release)
	return tx, release
}
func (f *fixture) waitLock(id int64) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	waitFor(f.t, ctx, func() bool {
		var n int
		err := f.admin.QueryRowContext(ctx, "SELECT COUNT(*) FROM performance_schema.data_lock_waits w JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID WHERE t.PROCESSLIST_ID=?", id).Scan(&n)
		must(f.t, err, "observe actual row wait")
		return n > 0
	}, "LOCK_WAIT_BARRIER")
}
func input(id string) domain.Input { return domain.Input{OperationID: id, SKU: "book", Quantity: 1} }
func writer() domain.Principal     { return domain.TeachingTokens()["Bearer lesson-writer"] }
func expectedBody(id, state string, quantity int64) string {
	return fmt.Sprintf(`{"operation_id":%q,"sku":"book","quantity":%d,"state":%q}`, id, quantity, state)
}
func errorBody(code string) string { return `{"error":{"code":"` + code + `"}}` }
func checkPublic(err error, want domain.Code, t *testing.T) {
	t.Helper()
	equal(t, domain.PublicCode(err), want, "PUBLIC_CODE")
}
func schemaSafe(s string) bool { return strings.HasPrefix(s, "reservation_") }

// Semantic assertions are attributed records; cleanup errors remain ordinary failures.
func semanticFailure(t *testing.T, marker, got, want string) {
	t.Helper()
	raw, err := json.Marshal(struct {
		Marker string `json:"marker"`
		Got    string `json:"got"`
		Want   string `json:"want"`
	}{marker, got, want})
	if err != nil {
		t.Fatal("semantic assertion encoding failed")
	}
	t.Fatalf("SEMANTIC_ASSERT %s", raw)
}

type finishRepository struct {
	domain.Repository
	done chan struct{}
}

func (r *finishRepository) Reserve(ctx context.Context, subject string, in domain.Input) (domain.Operation, error) {
	defer close(r.done)
	return r.Repository.Reserve(ctx, subject, in)
}

type countedRepository struct {
	domain.Repository
	calls *atomic.Int64
}

func (r *countedRepository) Reserve(ctx context.Context, subject string, in domain.Input) (domain.Operation, error) {
	r.calls.Add(1)
	return r.Repository.Reserve(ctx, subject, in)
}
func (r *countedRepository) Get(ctx context.Context, subject, id string) (domain.Operation, error) {
	r.calls.Add(1)
	return r.Repository.Get(ctx, subject, id)
}
func (r *countedRepository) List(ctx context.Context, subject string, limit int) ([]domain.Operation, error) {
	r.calls.Add(1)
	return r.Repository.List(ctx, subject, limit)
}
func observeEntries(f *fixture) (*atomic.Int64, *atomic.Int64) {
	app, repo := &atomic.Int64{}, &atomic.Int64{}
	f.service.OnEntry = func(string) { app.Add(1) }
	f.service.Repo = &countedRepository{Repository: f.repo, calls: repo}
	return app, repo
}

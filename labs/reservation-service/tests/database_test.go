//go:build integration

package tests

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync/atomic"
	"testing"
	"time"

	"example.com/reservation-service/internal/domain"
	"example.com/reservation-service/internal/store"
)

type reservationResult struct {
	op  domain.Operation
	err error
}

func reserveAsync(f *fixture, ctx context.Context, id string) <-chan reservationResult {
	done := make(chan reservationResult, 1)
	go func() { op, err := f.repo.Reserve(ctx, "alice", input(id)); done <- reservationResult{op, err} }()
	return done
}
func databaseCases() map[string]func(*fixture) {
	return map[string]func(*fixture){
		"D01": func(f *fixture) {
			op, err := f.repo.Reserve(context.Background(), "alice", input("op-a"))
			must(f.t, err, "reserve")
			equal(f.t, op, domain.Operation{OperationID: "op-a", SKU: "book", Quantity: 1, State: "confirmed"}, "DB_PAYLOAD")
			f.facts(9, 1)
			f.observe("op-a", "alice", "confirmed", 1)
			f.poolReturned()
		},
		"D02": func(f *fixture) {
			injected := errors.New("controlled rollback")
			f.setHooks(func(_ context.Context, stage string, _ int64) error {
				if stage == "debited" {
					return injected
				}
				return nil
			})
			_, err := f.repo.Reserve(context.Background(), "alice", input("op-a"))
			if !errors.Is(err, injected) {
				f.t.Fatal("ROLLBACK_ERROR: wrong injected identity")
			}
			var stock int64
			must(f.t, f.observer.QueryRow("SELECT stock FROM products WHERE sku='book'").Scan(&stock), "observe rollback")
			equal(f.t, stock, int64(10), "ROLLBACK_STOCK")
			f.facts(10, 0)
			f.poolReturned()
		},
		"D03": func(f *fixture) {
			_, err := f.observer.Exec("UPDATE products SET stock=1")
			must(f.t, err, "last item")
			entered := make(chan struct{}, 2)
			release := make(chan struct{})
			f.setHooks(func(_ context.Context, stage string, _ int64) error {
				if stage == "begin" {
					entered <- struct{}{}
					<-release
				}
				return nil
			})
			a := reserveAsync(f, context.Background(), "op-a")
			b := reserveAsync(f, context.Background(), "op-b")
			<-entered
			<-entered
			close(release)
			ra, rb := <-a, <-b
			must(f.t, ra.err, "first concurrent reserve")
			must(f.t, rb.err, "second concurrent reserve")
			states := []string{ra.op.State, rb.op.State}
			sort.Strings(states)
			equal(f.t, fmt.Sprint(states), "[confirmed rejected]", "LAST_ITEM_STATES")
			f.facts(0, 2)
			f.poolReturned()
		},
		"D04": func(f *fixture) {
			begins := make(chan int64, 2)
			claimed := make(chan struct{}, 1)
			release := make(chan struct{})
			var claims atomic.Int64
			f.setHooks(func(_ context.Context, stage string, id int64) error {
				if stage == "begin" {
					begins <- id
				}
				if stage == "claimed" && claims.Add(1) == 1 {
					claimed <- struct{}{}
					<-release
				}
				return nil
			})
			a := reserveAsync(f, context.Background(), "op-a")
			<-begins
			<-claimed
			b := reserveAsync(f, context.Background(), "op-a")
			id := <-begins
			f.waitLock(id)
			close(release)
			ra, rb := <-a, <-b
			must(f.t, ra.err, "first claim")
			must(f.t, rb.err, "duplicate claim")
			equal(f.t, ra.op, rb.op, "DUPLICATE_IDENTITY")
			equal(f.t, ra.op.State, "confirmed", "DUPLICATE_STATE")
			f.facts(9, 1)
			f.poolReturned()
		},
		"D05": func(f *fixture) {
			_, err := f.repo.Reserve(context.Background(), "alice", input("op-a"))
			must(f.t, err, "first")
			changed := input("op-a")
			changed.Quantity = 2
			_, err = f.repo.Reserve(context.Background(), "alice", changed)
			checkPublic(err, domain.Conflict, f.t)
			changed.SKU = "absent"
			_, err = f.repo.Reserve(context.Background(), "alice", changed)
			checkPublic(err, domain.Conflict, f.t)
			_, err = f.repo.Reserve(context.Background(), "bob", input("op-a"))
			must(f.t, err, "other subject")
			f.facts(8, 2)
			f.observe("op-a", "alice", "confirmed", 1)
			f.observe("op-a", "bob", "confirmed", 1)
		},
		"D06": func(f *fixture) {
			_, release := f.lockProduct()
			begins := make(chan int64, 1)
			f.setHooks(func(_ context.Context, stage string, id int64) error {
				if stage == "begin" {
					begins <- id
				}
				return nil
			})
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			done := reserveAsync(f, ctx, "op-a")
			id := <-begins
			f.waitLock(id)
			cancel()
			release()
			result := <-done
			if !errors.Is(result.err, context.Canceled) {
				semanticFailure(f.t, "CANCEL_IDENTITY", fmt.Sprintf("%T", result.err), "context.Canceled")
			}
			f.poolReturned()
			f.facts(10, 0)
		},
		"D07": func(f *fixture) {
			_, release := f.lockProduct()
			begins := make(chan int64, 1)
			f.setHooks(func(_ context.Context, stage string, id int64) error {
				if stage == "begin" {
					begins <- id
				}
				return nil
			})
			ctx, cancel := context.WithTimeout(context.Background(), 800*time.Millisecond)
			defer cancel()
			done := reserveAsync(f, ctx, "op-a")
			id := <-begins
			f.waitLock(id)
			<-ctx.Done()
			release()
			result := <-done
			if !errors.Is(result.err, context.DeadlineExceeded) {
				f.t.Fatalf("DEADLINE_IDENTITY: got %T", result.err)
			}
			f.poolReturned()
			f.facts(10, 0)
		},
		"D08": func(f *fixture) {
			f.db.SetMaxOpenConns(1)
			for _, id := range []string{"op-b", "op-a"} {
				_, err := f.repo.Reserve(context.Background(), "alice", input(id))
				must(f.t, err, "seed operation")
			}
			ops, err := f.repo.List(context.Background(), "alice", 32)
			must(f.t, err, "list")
			equal(f.t, len(ops), 2, "LIST_ROWS")
			equal(f.t, ops[0].OperationID, "op-a", "LIST_ORDER")
			_, err = f.repo.Get(context.Background(), "alice", "absent")
			checkPublic(err, domain.NotFound, f.t)
			f.setHooks(func(_ context.Context, stage string, _ int64) error {
				if stage == "claimed" {
					return errors.New("rollback")
				}
				return nil
			})
			_, err = f.repo.Reserve(context.Background(), "alice", input("op-c"))
			if err == nil {
				f.t.Fatal("EXPECTED_ROLLBACK")
			}
			f.poolReturned()
			f.facts(8, 2)
		},
		"D09": func(f *fixture) {
			proxy := newCommitProxy(f.t, f.dsn)
			defer proxy.Close()
			db, err := store.Open(proxy.DSN)
			must(f.t, err, "proxy DB")
			defer db.Close()
			var repo domain.Repository = &store.SQL{DB: db}
			if f.backend == "gorm" {
				repo, err = store.NewGORM(db, nil)
				must(f.t, err, "proxy gorm")
			}
			_, err = repo.Reserve(context.Background(), "alice", input("op-a"))
			checkPublic(err, domain.OutcomeUnknown, f.t)
			select {
			case <-proxy.Dropped:
			case <-time.After(time.Second):
				f.t.Fatal("COMMIT_ACK_NOT_DROPPED")
			}
			f.facts(9, 1)
			f.observe("op-a", "alice", "confirmed", 1)
			op, err := f.repo.Get(context.Background(), "alice", "op-a")
			must(f.t, err, "outcome lookup")
			equal(f.t, op.State, "confirmed", "UNKNOWN_LOOKUP")
			replayed, err := f.repo.Reserve(context.Background(), "alice", input("op-a"))
			must(f.t, err, "same key replay")
			equal(f.t, replayed, op, "UNKNOWN_REPLAY")
			f.facts(9, 1)
		},
		"D10": func(f *fixture) {
			f.setHooks(func(_ context.Context, stage string, id int64) error {
				if stage == "before_commit" {
					_, err := f.admin.Exec(fmt.Sprintf("KILL CONNECTION %d", id))
					return err
				}
				return nil
			})
			_, err := f.repo.Reserve(context.Background(), "alice", input("op-a"))
			checkPublic(err, domain.OutcomeUnknown, f.t)
			f.facts(10, 0)
			f.poolReturned()
		},
	}
}
func TestIntegration(t *testing.T) {
	for _, backend := range []string{"sql", "gorm"} {
		t.Run(backend, func(t *testing.T) {
			all := map[string]func(*fixture){}
			for _, set := range []map[string]func(*fixture){httpCases(), databaseCases(), grpcCases()} {
				for id, fn := range set {
					if _, ok := all[id]; ok {
						t.Fatal("duplicate case")
					}
					all[id] = fn
				}
			}
			ids := make([]string, 0, len(all))
			for id := range all {
				ids = append(ids, id)
			}
			sort.Strings(ids)
			for _, id := range ids {
				t.Run(id, func(t *testing.T) { f := newFixture(t, backend, 10); all[id](f); f.poolReturned() })
			}
		})
	}
}

//go:build integration

package tests

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	pb "example.com/reservation-service/api/reservation/v1"
	app "example.com/reservation-service/internal/runtime"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

type readyOutput struct {
	mu     sync.Mutex
	buffer bytes.Buffer
	ready  chan string
	sent   bool
}

func (o *readyOutput) Write(b []byte) (int, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	n, _ := o.buffer.Write(b)
	if !o.sent && strings.Contains(o.buffer.String(), "\n") {
		o.sent = true
		o.ready <- strings.SplitN(o.buffer.String(), "\n", 2)[0]
	}
	return n, nil
}

type child struct {
	cmd                *exec.Cmd
	httpAddr, grpcAddr string
	done               chan error
	out                *readyOutput
	stderr             bytes.Buffer
	waited             bool
}

func startChild(f *fixture, options ...string) *child {
	path := os.Getenv("RESERVATION_BIN")
	if path == "" {
		f.t.Fatal("REQUIRED_ENV: RESERVATION_BIN must be a separately built real process")
	}
	c := &child{done: make(chan error, 1), out: &readyOutput{ready: make(chan string, 1)}}
	c.cmd = exec.Command(path)
	c.cmd.Env = append(os.Environ(), "MYSQL_DSN="+f.dsn, "STORE="+f.backend, "HTTP_ADDR=127.0.0.1:0", "GRPC_ADDR=127.0.0.1:0", "ALLOW_INSECURE_TEACHING_NETWORK=")
	c.cmd.Env = append(c.cmd.Env, options...)
	c.cmd.Stdout = c.out
	c.cmd.Stderr = &c.stderr
	must(f.t, c.cmd.Start(), "child start")
	go func() { c.done <- c.cmd.Wait() }()
	f.t.Cleanup(func() {
		if !c.waited {
			_ = c.cmd.Process.Kill()
			<-c.done
		}
	})
	select {
	case line := <-c.out.ready:
		fields := strings.Fields(line)
		if len(fields) != 3 || fields[0] != "READY" {
			f.t.Fatal("PROCESS_READY_FORMAT")
		}
		c.httpAddr = strings.TrimPrefix(fields[1], "http=")
		c.grpcAddr = strings.TrimPrefix(fields[2], "grpc=")
	case err := <-c.done:
		c.waited = true
		f.t.Fatalf("PROCESS_START_EXIT: %T", err)
	case <-time.After(5 * time.Second):
		f.t.Fatal("PROCESS_READY_TIMEOUT")
	}
	return c
}
func (c *child) exit(t *testing.T) {
	t.Helper()
	select {
	case err := <-c.done:
		c.waited = true
		must(t, err, "process exit")
		equal(t, c.cmd.ProcessState.ExitCode(), 0, "PROCESS_EXIT_CODE")
		equal(t, c.stderr.String(), "", "PROCESS_STDERR")
	case <-time.After(6 * time.Second):
		t.Fatal("PROCESS_EXIT_TIMEOUT")
	}
}
func refuses(t *testing.T, address string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	waitFor(t, ctx, func() bool {
		conn, err := net.DialTimeout("tcp", address, 50*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			return false
		}
		return errors.Is(err, syscall.ECONNREFUSED)
	}, "LISTENER_REFUSES")
}
func (f *fixture) waitAnyLock() int64 {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	var connectionID int64
	waitFor(f.t, ctx, func() bool {
		err := f.admin.QueryRowContext(ctx, "SELECT COALESCE(MAX(t.PROCESSLIST_ID),0) FROM performance_schema.data_lock_waits w JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID JOIN performance_schema.data_locks l ON l.ENGINE_LOCK_ID=w.REQUESTING_ENGINE_LOCK_ID WHERE l.OBJECT_SCHEMA=?", f.schema).Scan(&connectionID)
		must(f.t, err, "process lock observation")
		return connectionID > 0
	}, "PROCESS_ACCEPTED_BARRIER")
	return connectionID
}

type processDBTarget struct {
	connectionID  int64
	threadID      int64
	transactionID string
}

func (f *fixture) waitProcessDBTarget() processDBTarget {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	var target processDBTarget
	waitFor(f.t, ctx, func() bool {
		var threads, transactions int
		err := f.admin.QueryRowContext(ctx, "SELECT COUNT(DISTINCT w.REQUESTING_THREAD_ID), COUNT(DISTINCT w.REQUESTING_ENGINE_TRANSACTION_ID), COALESCE(MAX(t.PROCESSLIST_ID),0), COALESCE(MAX(w.REQUESTING_THREAD_ID),0), COALESCE(CAST(MAX(w.REQUESTING_ENGINE_TRANSACTION_ID) AS CHAR),'') FROM performance_schema.data_lock_waits w JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID JOIN performance_schema.data_locks l ON l.ENGINE_LOCK_ID=w.REQUESTING_ENGINE_LOCK_ID WHERE l.OBJECT_SCHEMA=? AND l.OBJECT_NAME='products'", f.schema).Scan(&threads, &transactions, &target.connectionID, &target.threadID, &target.transactionID)
		must(f.t, err, "forced database target observation")
		if threads == 0 {
			return false
		}
		equal(f.t, threads, 1, "FORCED_DB_ONE_THREAD")
		equal(f.t, transactions, 1, "FORCED_DB_ONE_TRANSACTION")
		if target.connectionID <= 0 || target.threadID <= 0 || target.transactionID == "" || target.transactionID == "0" {
			f.t.Fatal("FORCED_DB_TARGET_IDENTITY")
		}
		return true
	}, "FORCED_DB_LOCK_BARRIER")
	return target
}

type processDBState struct {
	processes, threads, transactions, waits, locks int
}

func (f *fixture) processDBState(ctx context.Context, target processDBTarget) processDBState {
	var state processDBState
	err := f.admin.QueryRowContext(ctx, "SELECT (SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID=?), (SELECT COUNT(*) FROM performance_schema.threads WHERE THREAD_ID=?), (SELECT COUNT(*) FROM information_schema.INNODB_TRX WHERE TRX_ID=?), (SELECT COUNT(*) FROM performance_schema.data_lock_waits WHERE REQUESTING_THREAD_ID=? OR REQUESTING_ENGINE_TRANSACTION_ID=?), (SELECT COUNT(*) FROM performance_schema.data_locks WHERE THREAD_ID=? OR ENGINE_TRANSACTION_ID=?)", target.connectionID, target.threadID, target.transactionID, target.threadID, target.transactionID, target.threadID, target.transactionID).Scan(&state.processes, &state.threads, &state.transactions, &state.waits, &state.locks)
	must(f.t, err, "forced database state observation")
	return state
}

func (f *fixture) forcedFacts(ctx context.Context) {
	var stock int64
	var operations, pending int
	err := f.observer.QueryRowContext(ctx, "SELECT (SELECT stock FROM products WHERE sku='book'), (SELECT COUNT(*) FROM operations), (SELECT COUNT(*) FROM operations WHERE state='pending')").Scan(&stock, &operations, &pending)
	must(f.t, err, "forced independent facts")
	equal(f.t, stock, int64(10), "FORCED_PERSISTED_STOCK")
	equal(f.t, operations, 0, "FORCED_PERSISTED_OPERATIONS")
	equal(f.t, pending, 0, "FORCED_NO_COMMITTED_PENDING")
}

func TestProcess(t *testing.T) {
	t.Run("P01", func(t *testing.T) {
		f := newFixture(t, "sql", 10)
		_, release := f.lockProduct()
		c := startChild(f)
		req, err := http.NewRequest("POST", "http://"+c.httpAddr+"/v1/reservations", strings.NewReader(good))
		must(t, err, "process HTTP request")
		req.Header.Set("Authorization", "Bearer lesson-writer")
		req.Header.Set("Content-Type", "application/json")
		type response struct {
			status      int
			media, body string
			err         error
		}
		done := make(chan response, 1)
		go func() {
			resp, e := (&http.Client{Timeout: 4 * time.Second}).Do(req)
			if e != nil {
				done <- response{err: e}
				return
			}
			raw, e := io.ReadAll(resp.Body)
			if ce := resp.Body.Close(); e == nil {
				e = ce
			}
			done <- response{resp.StatusCode, resp.Header.Get("Content-Type"), string(raw), e}
		}()
		f.waitAnyLock()
		must(t, c.cmd.Process.Signal(syscall.SIGTERM), "SIGTERM")
		refuses(t, c.httpAddr)
		refuses(t, c.grpcAddr)
		release()
		got := <-done
		must(t, got.err, "drained complete HTTP body")
		equal(t, got.status, 200, "DRAINED_HTTP_STATUS")
		equal(t, got.media, "application/json", "DRAINED_HTTP_MEDIA")
		equal(t, got.body, expectedBody("op-a", "confirmed", 1), "DRAINED_HTTP_BODY")
		c.exit(t)
		f.facts(9, 1)
	})
	t.Run("P02", func(t *testing.T) {
		f := newFixture(t, "gorm", 10)
		_, release := f.lockProduct()
		c := startChild(f)
		conn, err := grpc.NewClient(c.grpcAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
		must(t, err, "process grpc dial")
		defer conn.Close()
		client := pb.NewReservationServiceClient(conn)
		type response struct {
			op  *pb.Operation
			err error
		}
		done := make(chan response, 1)
		ctx, cancel := context.WithTimeout(rpcContext("Bearer lesson-writer"), 4*time.Second)
		defer cancel()
		go func() { op, e := client.Reserve(ctx, rpcInput("op-a")); done <- response{op, e} }()
		f.waitAnyLock()
		must(t, c.cmd.Process.Signal(syscall.SIGTERM), "SIGTERM")
		refuses(t, c.httpAddr)
		refuses(t, c.grpcAddr)
		release()
		got := <-done
		must(t, got.err, "drained grpc response")
		rpcPayload(t, got.op, "op-a", "confirmed", 1)
		c.exit(t)
		ctx2, cancel2 := context.WithTimeout(rpcContext("Bearer lesson-reader"), time.Second)
		defer cancel2()
		_, err = client.Get(ctx2, &pb.GetRequest{OperationId: "op-a"})
		equal(t, status.Code(err), codes.Unavailable, "POST_STOP_GRPC")
		f.facts(9, 1)
	})
	t.Run("P03", func(t *testing.T) {
		f := newFixture(t, "sql", 10)
		r := app.New(f.db, f.service)
		hl, err := net.Listen("tcp", "127.0.0.1:0")
		must(t, err, "runtime http")
		gl, err := net.Listen("tcp", "127.0.0.1:0")
		must(t, err, "runtime grpc")
		r.Start(hl, gl)
		for _, path := range []string{"/live", "/ready"} {
			resp, e := http.Get("http://" + hl.Addr().String() + path)
			must(t, e, "health read")
			raw, e := io.ReadAll(resp.Body)
			must(t, e, "health complete body")
			must(t, resp.Body.Close(), "health close")
			equal(t, resp.StatusCode, 200, "HEALTH_STATUS")
			want := `{"status":"live"}`
			if path == "/ready" {
				want = `{"status":"ready"}`
			}
			equal(t, string(raw), want, "HEALTH_BODY")
		}
		// Closing the pool proves that readiness depends on DB reachability, while liveness does not.
		must(t, f.db.Close(), "controlled pool close")
		resp, err := http.Get("http://" + hl.Addr().String() + "/ready")
		must(t, err, "unready response")
		raw, err := io.ReadAll(resp.Body)
		must(t, err, "unready body")
		must(t, resp.Body.Close(), "unready close")
		equal(t, resp.StatusCode, 503, "DB_NOT_READY_STATUS")
		equal(t, string(raw), errorBody("not_ready"), "DB_NOT_READY_BODY")
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		must(t, r.Shutdown(ctx), "runtime shutdown")
		select {
		case <-r.Stopped():
		default:
			t.Fatal("OWNED_GOROUTINES_NOT_JOINED")
		}
		refuses(t, hl.Addr().String())
		refuses(t, gl.Addr().String())
		if err = f.db.Ping(); err == nil || !strings.Contains(err.Error(), "database is closed") {
			t.Fatalf("POOL_CLOSED: %T", err)
		}
		// No claim about unrelated runtime goroutines; component joins are explicit.
		if e := r.Shutdown(ctx); e != nil && !errors.Is(e, context.Canceled) {
			t.Fatal("idempotent shutdown")
		}
	})
	t.Run("P04", func(t *testing.T) {
		f := newFixture(t, "sql", 10)
		_, release := f.lockProduct()
		c := startChild(f, "SHUTDOWN_GRACE=250ms")
		req, err := http.NewRequest("POST", "http://"+c.httpAddr+"/v1/reservations", strings.NewReader(good))
		must(t, err, "forced shutdown request")
		req.Header.Set("Authorization", "Bearer lesson-writer")
		req.Header.Set("Content-Type", "application/json")
		type response struct {
			response *http.Response
			err      error
		}
		clientDone := make(chan response, 1)
		go func() { resp, e := (&http.Client{Timeout: 4 * time.Second}).Do(req); clientDone <- response{resp, e} }()
		target := f.waitProcessDBTarget()
		must(t, c.cmd.Process.Signal(syscall.SIGTERM), "forced SIGTERM")
		// Keep the database lock until the real child process has exited.
		refuses(t, c.httpAddr)
		refuses(t, c.grpcAddr)
		select {
		case err = <-c.done:
			c.waited = true
			var exit *exec.ExitError
			if !errors.As(err, &exit) {
				t.Fatalf("FORCED_PROCESS_EXIT: expected ExitError, got %T", err)
			}
			equal(t, exit.ExitCode(), 1, "FORCED_PROCESS_EXIT_CODE")
			equal(t, c.cmd.ProcessState.ExitCode(), 1, "FORCED_PROCESS_STATE")
			equal(t, c.stderr.String(), "shutdown deadline exceeded\n", "FORCED_PROCESS_STDERR")
		case <-time.After(2 * time.Second):
			t.Fatal("FORCED_PROCESS_EXIT_TIMEOUT")
		}
		got := <-clientDone
		if got.response != nil {
			_ = got.response.Body.Close()
			t.Fatal("FORCED_HTTP_UNEXPECTED_RESPONSE")
		}
		if !errors.Is(got.err, io.EOF) {
			t.Fatalf("FORCED_HTTP_ERROR: expected EOF, got %T", got.err)
		}
		// Client exit does not synchronously remove a MySQL thread waiting on our lock.
		// Record either state without requiring the server thread to remain present.
		before, beforeCancel := context.WithTimeout(context.Background(), time.Second)
		defer beforeCancel()
		observed := f.processDBState(before, target)
		t.Logf("FORCED_DB_BEFORE_RELEASE processes=%d threads=%d transactions=%d waits=%d locks=%d", observed.processes, observed.threads, observed.transactions, observed.waits, observed.locks)
		f.forcedFacts(before)
		release()
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		waitFor(t, ctx, func() bool {
			return f.processDBState(ctx, target) == (processDBState{})
		}, "FORCED_DB_RESOURCES_GONE")
		f.forcedFacts(ctx)
		refuses(t, c.httpAddr)
		refuses(t, c.grpcAddr)
		// Wait reaped the actual default-entry child; its owned listener processes ended with it.
		equal(t, c.cmd.ProcessState.Exited(), true, "FORCED_PROCESS_REAPED")
	})

}

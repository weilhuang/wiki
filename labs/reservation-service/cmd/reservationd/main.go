package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"example.com/reservation-service/internal/domain"
	app "example.com/reservation-service/internal/runtime"
	"example.com/reservation-service/internal/store"
	"example.com/reservation-service/migrations"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
}
func setting(key, fallback string) string {
	if s := os.Getenv(key); s != "" {
		return s
	}
	return fallback
}
func safeAddress(addr string) error {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return errors.New("invalid listen address")
	}
	ip := net.ParseIP(host)
	if (ip == nil || !ip.IsLoopback()) && os.Getenv("ALLOW_INSECURE_TEACHING_NETWORK") != "yes" {
		return errors.New("non-loopback teaching transport requires explicit opt-in")
	}
	return nil
}
func shutdownGrace(value string) (time.Duration, error) {
	if value == "" {
		return 5 * time.Second, nil
	}
	grace, err := time.ParseDuration(value)
	if err != nil || grace < 50*time.Millisecond || grace > 30*time.Second {
		return 0, errors.New("SHUTDOWN_GRACE must be 50ms..30s")
	}
	return grace, nil
}
func run() error {
	grace, err := shutdownGrace(os.Getenv("SHUTDOWN_GRACE"))
	if err != nil {
		return err
	}
	migrate := flag.Bool("migrate", false, "apply explicit migration to a fresh schema and exit")
	flag.Parse()
	dsn := os.Getenv("MYSQL_DSN")
	if dsn == "" {
		return errors.New("MYSQL_DSN is required")
	}
	db, err := store.Open(dsn)
	if err != nil {
		return errors.New("database configuration failed")
	}
	defer db.Close()
	startup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err = db.PingContext(startup); err != nil {
		return errors.New("database startup check failed")
	}
	if *migrate {
		if err = migrations.Apply(startup, db); err != nil {
			return errors.New("migration failed")
		}
		return nil
	}
	for _, q := range []string{"SELECT sku,stock FROM products LIMIT 0", "SELECT subject,operation_id,sku,quantity,state FROM operations LIMIT 0"} {
		rows, e := db.QueryContext(startup, q)
		if e != nil {
			return errors.New("schema startup check failed")
		}
		if e = rows.Close(); e != nil {
			return errors.New("schema startup check failed")
		}
	}
	var repo domain.Repository
	switch setting("STORE", "sql") {
	case "sql":
		repo = &store.SQL{DB: db}
	case "gorm":
		repo, err = store.NewGORM(db, nil)
		if err != nil {
			return errors.New("gorm startup failed")
		}
	default:
		return errors.New("STORE must be sql or gorm")
	}
	httpAddr := setting("HTTP_ADDR", "127.0.0.1:8080")
	grpcAddr := setting("GRPC_ADDR", "127.0.0.1:9090")
	if err = safeAddress(httpAddr); err != nil {
		return err
	}
	if err = safeAddress(grpcAddr); err != nil {
		return err
	}
	hl, err := net.Listen("tcp", httpAddr)
	if err != nil {
		return errors.New("http listen failed")
	}
	defer hl.Close()
	gl, err := net.Listen("tcp", grpcAddr)
	if err != nil {
		return errors.New("grpc listen failed")
	}
	defer gl.Close()
	r := app.New(db, &domain.Service{Repo: repo})
	r.Start(hl, gl)
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(sig)
	// Report only listener addresses, never DSN, environment, or SQL errors.
	fmt.Printf("READY http=%s grpc=%s\n", hl.Addr(), gl.Addr())
	var serveErr error
	select {
	case <-sig:
	case serveErr = <-r.Errors:
	}
	shutdown, done := context.WithTimeout(context.Background(), grace)
	defer done()
	if err = r.Shutdown(shutdown); err != nil {
		return errors.New("shutdown deadline exceeded")
	}
	return serveErr
}

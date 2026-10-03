package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const responseBody = "{\"message\":\"wiki-bootstrap\"}\n"

func handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		io.WriteString(w, "ready\n")
	})
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		io.WriteString(w, responseBody)
	})
	return mux
}
func probe(url string) error {
	c := &http.Client{
		Timeout: 5 * time.Second,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	res, err := c.Get(url)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	body, err := io.ReadAll(io.LimitReader(res.Body, 1024))
	if err != nil {
		return err
	}
	if res.StatusCode != http.StatusOK || string(body) != responseBody || res.Header.Get("Content-Type") != "application/json" {
		return fmt.Errorf("unexpected response: status=%d body=%q", res.StatusCode, body)
	}
	fmt.Print(string(body))
	return nil
}
func run() error {
	url := flag.String("url", "", "Make one bounded HTTP assertion instead of serving")
	flag.Parse()
	if *url != "" {
		return probe(*url)
	}
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()
	server := &http.Server{Addr: ":8080", Handler: handler(), ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second, IdleTimeout: 15 * time.Second}
	ended := make(chan error, 1)
	go func() { ended <- server.ListenAndServe() }()
	select {
	case err := <-ended:
		return err
	case <-ctx.Done():
		shutdown, stop := context.WithTimeout(context.Background(), 5*time.Second)
		defer stop()
		if err := server.Shutdown(shutdown); err != nil {
			return err
		}
		err := <-ended
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

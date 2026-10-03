//go:build integration

package tests

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"time"

	"example.com/reservation-service/internal/domain"
	"example.com/reservation-service/internal/httpapi"
)

type httpFixture struct {
	*fixture
	server  *httptest.Server
	entries atomic.Int64
}

func httpFor(f *fixture) *httpFixture {
	h := &httpFixture{fixture: f}
	f.service.OnEntry = func(string) { h.entries.Add(1) }
	h.server = httptest.NewServer((&httpapi.API{Service: f.service, Tokens: domain.TeachingTokens()}).Handler())
	f.t.Cleanup(h.server.Close)
	return h
}
func (h *httpFixture) request(method, path, body, token, media string, wantStatus int, wantBody, marker string) {
	h.t.Helper()
	req, err := http.NewRequest(method, h.server.URL+path, strings.NewReader(body))
	must(h.t, err, "request")
	if token != "" {
		req.Header.Set("Authorization", token)
	}
	if media != "" {
		req.Header.Set("Content-Type", media)
	}
	h.check(req, wantStatus, wantBody, marker)
}
func (h *httpFixture) check(req *http.Request, wantStatus int, wantBody, marker string) {
	h.t.Helper()
	client := &http.Client{Timeout: 4 * time.Second}
	resp, err := client.Do(req)
	must(h.t, err, "HTTP response")
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	must(h.t, err, "HTTP complete body read")
	equal(h.t, resp.StatusCode, wantStatus, marker+"_STATUS")
	equal(h.t, resp.Header.Get("Content-Type"), "application/json", marker+"_MEDIA")
	equal(h.t, string(raw), wantBody, marker)
}

const good = `{"operation_id":"op-a","sku":"book","quantity":1}`

func httpCases() map[string]func(*fixture) {
	return map[string]func(*fixture){
		"H01": func(f *fixture) {
			h := httpFor(f)
			h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", 200, expectedBody("op-a", "confirmed", 1), "HTTP_SUCCESS")
			equal(f.t, h.entries.Load(), int64(1), "HTTP_ENTRIES")
			f.facts(9, 1)
			f.observe("op-a", "alice", "confirmed", 1)
		},
		"H02": func(f *fixture) {
			h := httpFor(f)
			for _, token := range []string{"", "Bearer wrong"} {
				h.request("POST", "/v1/reservations", "broken", token, "text/plain", 401, errorBody("unauthenticated"), "HTTP_IDENTITY")
			}
			req, err := http.NewRequest("POST", h.server.URL+"/v1/reservations", strings.NewReader(good))
			must(f.t, err, "request")
			req.Header.Add("Authorization", "Bearer lesson-writer")
			req.Header.Add("Authorization", "Bearer lesson-reader")
			h.check(req, 401, errorBody("unauthenticated"), "HTTP_MULTIPLE_IDENTITY")
			equal(f.t, h.entries.Load(), int64(0), "HTTP_REJECT_ENTRIES")
			f.facts(10, 0)
		},
		"H03": func(f *fixture) {
			h := httpFor(f)
			h.request("POST", "/v1/reservations", good, "Bearer lesson-reader", "application/json", 403, errorBody("permission_denied"), "HTTP_FORBIDDEN")
			h.request("POST", "/v1/reservations", "broken", "Bearer lesson-reader", "text/plain", 403, errorBody("permission_denied"), "HTTP_FORBIDDEN_ORDER")
			equal(f.t, h.entries.Load(), int64(0), "HTTP_REJECT_ENTRIES")
			f.facts(10, 0)
		},
		"H04": func(f *fixture) {
			h := httpFor(f)
			for _, media := range []string{"", "text/plain", "application/json;charset=latin1", "application/json;x=1"} {
				h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", media, 415, errorBody("unsupported_media_type"), "HTTP_MEDIA")
			}
			equal(f.t, h.entries.Load(), int64(0), "HTTP_REJECT_ENTRIES")
			h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json;charset=utf-8", 200, expectedBody("op-a", "confirmed", 1), "HTTP_CHARSET")
			f.facts(9, 1)
		},
		"H05": func(f *fixture) {
			h := httpFor(f)
			for _, body := range []string{`{`, `null`, `[]`, `{}`, `{"operation_id":"op-a","sku":"book"}`, `{"operation_id":"op-a","sku":"book","quantity":null}`, `{"operation_id":"op-a","sku":"book","quantity":1.0}`, `{"operation_id":"op-a","sku":"book","quantity":1,"x":0}`, `{"operation_id":"op-a","sku":"book","quantity":1,"quantity":2}`, `{"operation_id":"op-a","sku":"book","quantity":1,"qu\u0061ntity":2}`, good + ` {}`} {
				h.request("POST", "/v1/reservations", body, "Bearer lesson-writer", "application/json", 400, errorBody("invalid_json"), "HTTP_JSON")
			}
			equal(f.t, h.entries.Load(), int64(0), "HTTP_REJECT_ENTRIES")
			f.facts(10, 0)
		},
		"H06": func(f *fixture) {
			h := httpFor(f)
			h.request("POST", "/v1/reservations", good+strings.Repeat(" ", 1025-len(good)), "Bearer lesson-writer", "application/json", 413, errorBody("body_too_large"), "HTTP_BODY_LIMIT")
			equal(f.t, h.entries.Load(), int64(0), "HTTP_REJECT_ENTRIES")
			addr := strings.TrimPrefix(h.server.URL, "http://")
			conn, err := net.DialTimeout("tcp", addr, time.Second)
			must(f.t, err, "raw dial")
			defer conn.Close()
			must(f.t, conn.SetDeadline(time.Now().Add(2*time.Second)), "raw deadline")
			_, err = fmt.Fprintf(conn, "POST /v1/reservations HTTP/1.1\r\nHost: lesson\r\nAuthorization: Bearer lesson-writer\r\nContent-Type: application/json\r\nContent-Length: 99\r\nConnection: close\r\n\r\n{")
			must(f.t, err, "raw write")
			must(f.t, conn.(*net.TCPConn).CloseWrite(), "raw half close")
			resp, err := http.ReadResponse(bufio.NewReader(conn), nil)
			must(f.t, err, "truncated response")
			raw, err := io.ReadAll(resp.Body)
			must(f.t, err, "truncated response body")
			must(f.t, resp.Body.Close(), "truncated body close")
			equal(f.t, resp.StatusCode, 400, "HTTP_READ_STATUS")
			equal(f.t, resp.Header.Get("Content-Type"), "application/json", "HTTP_READ_MEDIA")
			equal(f.t, string(raw), errorBody("body_read_failed"), "HTTP_READ_ERROR")
			equal(f.t, h.entries.Load(), int64(0), "HTTP_READ_REJECT_ENTRIES")
			f.facts(10, 0)
			h.request("POST", "/v1/reservations", good+strings.Repeat(" ", 1024-len(good)), "Bearer lesson-writer", "application/json", 200, expectedBody("op-a", "confirmed", 1), "HTTP_EXACT_LIMIT")
			f.facts(9, 1)
		},
		"H07": func(f *fixture) {
			h := httpFor(f)
			for _, body := range []string{strings.Replace(good, `:1}`, `:0}`, 1), strings.Replace(good, `:1}`, `:-1}`, 1), strings.Replace(good, `:1}`, `:101}`, 1), strings.Replace(good, "op-a", "BAD", 1), strings.Replace(good, "book", "x/y", 1)} {
				h.request("POST", "/v1/reservations", body, "Bearer lesson-writer", "application/json", 400, errorBody("invalid_argument"), "HTTP_ARGUMENT")
			}
			f.facts(10, 0)
		},
		"H08": func(f *fixture) {
			h := httpFor(f)
			for i := 0; i < 2; i++ {
				h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", 200, expectedBody("op-a", "confirmed", 1), "HTTP_REPLAY")
			}
			h.request("POST", "/v1/reservations", strings.Replace(good, `:1}`, `:2}`, 1), "Bearer lesson-writer", "application/json", 409, errorBody("operation_conflict"), "HTTP_CONFLICT")
			f.facts(9, 1)
			f.observe("op-a", "alice", "confirmed", 1)
		},
		"H09": func(f *fixture) {
			_, err := f.observer.Exec("UPDATE products SET stock=0")
			must(f.t, err, "empty stock")
			h := httpFor(f)
			h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", 409, errorBody("out_of_stock"), "HTTP_OUT_OF_STOCK")
			h.request("GET", "/v1/reservations/op-a", "", "Bearer lesson-reader", "", 200, expectedBody("op-a", "rejected", 1), "HTTP_LOOKUP_REJECTED")
			_, err = f.observer.Exec("UPDATE products SET stock=10")
			must(f.t, err, "refill")
			h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", 409, errorBody("out_of_stock"), "HTTP_REPLAY_REJECTED")
			h.request("GET", "/v1/reservations/op-a", "", "Bearer lesson-other", "", 404, errorBody("not_found"), "HTTP_OWNER")
			f.facts(10, 1)
			f.observe("op-a", "alice", "rejected", 1)
		},
		"H10": func(f *fixture) {
			for _, tc := range []struct {
				cause  error
				status int
				code   string
			}{
				{errors.New("private database detail"), 500, "internal"},
				{context.Canceled, 499, "canceled"},
				{context.DeadlineExceeded, 504, "deadline_exceeded"},
				{domain.Fail(domain.OutcomeUnknown, errors.New("private commit detail")), 503, "outcome_unknown"},
			} {
				f.setHooks(func(context.Context, string, int64) error { return tc.cause })
				h := httpFor(f)
				h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", tc.status, errorBody(tc.code), "HTTP_ERROR_BODY")
				equal(f.t, h.entries.Load(), int64(1), "HTTP_MAPPING_ENTRIES")
				f.facts(10, 0)
			}
			f.setHooks(nil)
			h := httpFor(f)
			h.request("POST", "/v1/reservations", strings.Replace(good, "book", "absent", 1), "Bearer lesson-writer", "application/json", 404, errorBody("not_found"), "HTTP_UNKNOWN_PRODUCT")
			equal(f.t, h.entries.Load(), int64(1), "HTTP_UNKNOWN_ENTRIES")
			f.facts(10, 0)
		},
		"H11": func(f *fixture) {
			_, release := f.lockProduct()
			type seen struct {
				ctx context.Context
				id  int64
			}
			entered := make(chan seen, 1)
			f.setHooks(func(ctx context.Context, stage string, id int64) error {
				if stage == "begin" {
					entered <- seen{ctx, id}
				}
				return nil
			})
			finished := make(chan struct{})
			f.service.Repo = &finishRepository{Repository: f.repo, done: finished}
			h := httpFor(f)
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			req, err := http.NewRequestWithContext(ctx, "POST", h.server.URL+"/v1/reservations", strings.NewReader(good))
			must(f.t, err, "cancel request")
			req.Header.Set("Authorization", "Bearer lesson-writer")
			req.Header.Set("Content-Type", "application/json")
			done := make(chan error, 1)
			go func() {
				resp, e := http.DefaultClient.Do(req)
				if resp != nil {
					_ = resp.Body.Close()
				}
				done <- e
			}()
			s := <-entered
			f.waitLock(s.id)
			cancel()
			err = <-done
			if !errors.Is(err, context.Canceled) {
				f.t.Fatal("HTTP_CANCEL_CLIENT: expected context.Canceled")
			}
			select {
			case <-s.ctx.Done():
			case <-time.After(time.Second):
				f.t.Fatal("HTTP_CANCEL_SERVER: no cancellation")
			}
			release()
			select {
			case <-finished:
			case <-time.After(time.Second):
				f.t.Fatal("HTTP_REPOSITORY_NOT_FINISHED")
			}
			f.poolReturned()
			f.facts(10, 0)
		},
	}
}

package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
)

func TestHTTPContract(t *testing.T) {
	s := httptest.NewServer(handler())
	defer s.Close()
	// Expected public bytes are a literal in the test, independent of the implementation constant.
	r, err := http.Get(s.URL)
	if err != nil {
		t.Fatal(err)
	}
	b, err := io.ReadAll(r.Body)
	r.Body.Close()
	if err != nil || r.StatusCode != 200 || string(b) != "{\"message\":\"wiki-bootstrap\"}\n" || r.Header.Get("Content-Type") != "application/json" {
		t.Fatalf("HTTP contract: %d %q %v", r.StatusCode, b, err)
	}
	if err := probe(s.URL); err != nil {
		t.Fatal(err)
	}
	r, err = http.Get(s.URL + "/readyz")
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	b, err = io.ReadAll(r.Body)
	if err != nil || r.StatusCode != 200 || string(b) != "ready\n" {
		t.Fatalf("readiness contract: %d %q %v", r.StatusCode, b, err)
	}
}
func TestProbeRejectsWrongResponse(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("wrong\n")) }))
	defer s.Close()
	if probe(s.URL) == nil {
		t.Fatal("probe accepted wrong body")
	}
}

func TestProbeRejectsRedirect(t *testing.T) {
	var targetHits atomic.Int32
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		targetHits.Add(1)
		w.Header().Set("Content-Type", "application/json")
		io.WriteString(w, "{\"message\":\"wiki-bootstrap\"}\n")
	}))
	defer target.Close()
	redirect := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL, http.StatusFound)
	}))
	defer redirect.Close()
	if err := probe(redirect.URL); err == nil {
		t.Fatal("probe accepted a redirect to an otherwise valid target")
	}
	if got := targetHits.Load(); got != 0 {
		t.Fatalf("probe followed redirect: target requests=%d", got)
	}
}

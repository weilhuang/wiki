// SPDX-License-Identifier: MIT
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"runtime/trace"
	"sync"
	"sync/atomic"
	"time"
)

type report struct {
	Scenario                  string `json:"scenario"`
	Version                   string `json:"version"`
	Status                    string `json:"status"`
	Started                   int    `json:"started"`
	Joined                    int    `json:"joined"`
	Completed                 int64  `json:"completed"`
	ApplicationGoroutineLimit int    `json:"applicationGoroutineLimit"`
	BlockedObserved           int    `json:"blockedObserved"`
	ActiveAtSnapshot          int64  `json:"activeAtSnapshot"`
	WaitingAtSnapshot         int64  `json:"waitingAtSnapshot"`
	CPUChecksum               uint64 `json:"cpuChecksum"`
	NetworkBytes              int64  `json:"networkBytes"`
	Error                     string `json:"error,omitempty"`
}

//go:noinline
func cpuWork(stop *atomic.Bool, started chan<- struct{}) uint64 {
	close(started)
	x := uint64(1)
	for !stop.Load() {
		for range 100000 {
			x = x*1664525 + 1013904223
			x ^= x >> 13
		}
	}
	return x
}

//go:noinline
func channelWait(release <-chan struct{}, started chan<- struct{}) {
	close(started)
	<-release
}

//go:noinline
func networkWait(c net.Conn, started chan<- struct{}) (int, error) {
	close(started)
	var b [1]byte
	n, err := io.ReadFull(c, b[:])
	if err == nil && b[0] != 'K' {
		return n, fmt.Errorf("NETWORK_VALUE got=%q", b[0])
	}
	return n, err
}

//go:noinline
func activeWork(release <-chan struct{}) { <-release }

//go:noinline
func queuedWork(permit chan struct{}, release <-chan struct{}, entered chan<- struct{}, active, complete *atomic.Int64) {
	entered <- struct{}{}
	permit <- struct{}{}
	active.Add(1)
	activeWork(release)
	active.Add(-1)
	<-permit
	complete.Add(1)
}

// The polling timer observes a real stack state, not guessed worker progress.
// Work remains held by explicit release gates until the snapshot is accepted.
func capture(ctx context.Context, function, state string, want int) ([]byte, int, error) {
	ticker := time.NewTicker(5 * time.Millisecond)
	defer ticker.Stop()
	for {
		buf := make([]byte, 1<<20)
		n := runtime.Stack(buf, true)
		if n == len(buf) {
			return nil, 0, errors.New("STACK_TRUNCATED")
		}
		buf = buf[:n]
		count := 0
		for _, block := range bytes.Split(buf, []byte("\n\n")) {
			if bytes.Contains(block, []byte(function)) && bytes.Contains(bytes.SplitN(block, []byte("\n"), 2)[0], []byte(state)) {
				count++
			}
		}
		if count >= want {
			return buf, count, nil
		}
		select {
		case <-ctx.Done():
			return nil, count, fmt.Errorf("OBSERVATION_TIMEOUT %s state=%s count=%d want=%d: %w", function, state, count, want, ctx.Err())
		case <-ticker.C:
		}
	}
}

func run(scenario, output string, failWorker bool) (r report, result error) {
	r = report{Scenario: scenario, Version: runtime.Version(), Status: "fail"}
	if scenario != "cpu" && scenario != "channel" && scenario != "network" && scenario != "backlog" {
		return r, errors.New("INVALID_SCENARIO")
	}
	if err := os.MkdirAll(output, 0700); err != nil {
		return r, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	runtime.GOMAXPROCS(2)
	runtime.SetBlockProfileRate(1)
	defer runtime.SetBlockProfileRate(0)
	tf, err := os.Create(filepath.Join(output, "trace.out"))
	if err != nil {
		return r, err
	}
	defer func() { result = errors.Join(result, tf.Close()) }()
	if err = trace.Start(tf); err != nil {
		return r, err
	}
	defer trace.Stop()
	cf, err := os.Create(filepath.Join(output, "cpu.pprof"))
	if err != nil {
		return r, err
	}
	defer func() { result = errors.Join(result, cf.Close()) }()
	if err = pprof.StartCPUProfile(cf); err != nil {
		return r, err
	}
	defer pprof.StopCPUProfile()
	var wg sync.WaitGroup
	var stop atomic.Bool
	var active, complete, networkBytes atomic.Int64
	var checksum atomic.Uint64
	release := make(chan struct{})
	var releaseOnce sync.Once
	releaseAll := func() { releaseOnce.Do(func() { close(release) }); stop.Store(true) }
	errs := make(chan error, 24)
	var conns []net.Conn
	cleanup := func() {
		releaseAll()
		for _, c := range conns {
			_ = c.Close()
		}
		wg.Wait()
	}
	defer cleanup()
	spawn := func(f func() error) {
		r.Started++
		wg.Add(1)
		go func() {
			defer wg.Done()
			if e := f(); e != nil {
				errs <- e
			}
		}()
	}
	var stack []byte
	switch scenario {
	case "cpu":
		r.ApplicationGoroutineLimit = 1
		entered := make(chan struct{})
		spawn(func() error { checksum.Store(cpuWork(&stop, entered)); complete.Add(1); return nil })
		<-entered
		select {
		case <-time.After(450 * time.Millisecond):
		case <-ctx.Done():
			return r, ctx.Err()
		}
		stack = make([]byte, 1<<20)
		n := runtime.Stack(stack, true)
		if n == len(stack) {
			return r, errors.New("STACK_TRUNCATED")
		}
		stack = stack[:n]
	case "channel":
		r.ApplicationGoroutineLimit = 1
		entered := make(chan struct{})
		spawn(func() error { channelWait(release, entered); complete.Add(1); return nil })
		<-entered
		stack, r.BlockedObserved, err = capture(ctx, "main.channelWait", "[chan receive]", 1)
	case "network":
		r.ApplicationGoroutineLimit = 2 // One temporary accept worker, then one read worker.
		ln, e := net.Listen("tcp4", "127.0.0.1:0")
		if e != nil {
			return r, fmt.Errorf("LISTEN_FAILED: %w", e)
		}
		tcpLn := ln.(*net.TCPListener)
		if e = tcpLn.SetDeadline(time.Now().Add(2 * time.Second)); e != nil {
			_ = ln.Close()
			return r, e
		}
		accepted := make(chan net.Conn, 1)
		acceptErr := make(chan error, 1)
		var acceptWG sync.WaitGroup
		acceptWG.Add(1)
		go func() {
			defer acceptWG.Done()
			c, e := ln.Accept()
			if e != nil {
				acceptErr <- e
			} else {
				accepted <- c
			}
		}()
		client, e := net.DialTimeout("tcp4", ln.Addr().String(), 2*time.Second)
		if e != nil {
			_ = ln.Close()
			acceptWG.Wait()
			return r, fmt.Errorf("DIAL_FAILED: %w", e)
		}
		conns = append(conns, client)
		var peer net.Conn
		select {
		case peer = <-accepted:
			conns = append(conns, peer)
		case e = <-acceptErr:
			_ = ln.Close()
			acceptWG.Wait()
			return r, fmt.Errorf("ACCEPT_FAILED: %w", e)
		case <-ctx.Done():
			_ = ln.Close()
			acceptWG.Wait()
			return r, ctx.Err()
		}
		_ = ln.Close()
		acceptWG.Wait()
		if e = client.SetDeadline(time.Now().Add(2 * time.Second)); e != nil {
			return r, e
		}
		if e = peer.SetDeadline(time.Now().Add(2 * time.Second)); e != nil {
			return r, e
		}
		entered := make(chan struct{})
		spawn(func() error {
			n, e := networkWait(client, entered)
			networkBytes.Store(int64(n))
			if e != nil {
				return fmt.Errorf("WORKER_ERROR: %w", e)
			}
			complete.Add(1)
			return nil
		})
		<-entered
		stack, r.BlockedObserved, err = capture(ctx, "main.networkWait", "[IO wait]", 1)
		if err == nil {
			if failWorker {
				_ = peer.Close()
			} else {
				_, err = peer.Write([]byte{'K'})
			}
		}
	case "backlog":
		r.ApplicationGoroutineLimit = 24
		entered := make(chan struct{}, 24)
		permit := make(chan struct{}, 2)
		for range 24 {
			spawn(func() error { queuedWork(permit, release, entered, &active, &complete); return nil })
		}
		for range 24 {
			<-entered
		}
		stack, r.BlockedObserved, err = capture(ctx, "main.queuedWork", "[chan send]", 22)
		r.ActiveAtSnapshot = active.Load()
		r.WaitingAtSnapshot = int64(r.BlockedObserved)
		if err == nil && (r.ActiveAtSnapshot != 2 || r.BlockedObserved != 22) {
			err = fmt.Errorf("BACKLOG_ACCOUNTING active=%d waiting=%d", r.ActiveAtSnapshot, r.BlockedObserved)
		}
	}
	if err != nil {
		return r, err
	}
	if err = os.WriteFile(filepath.Join(output, "goroutines.txt"), stack, 0600); err != nil {
		return r, err
	}
	releaseAll()
	wg.Wait()
	r.Joined = r.Started
	close(errs)
	for e := range errs {
		result = errors.Join(result, e)
	}
	r.Completed = complete.Load()
	r.CPUChecksum = checksum.Load()
	r.NetworkBytes = networkBytes.Load()
	for _, c := range conns {
		if e := c.Close(); e != nil && !errors.Is(e, net.ErrClosed) {
			result = errors.Join(result, e)
		}
	}
	if r.Completed != int64(r.Started) {
		result = errors.Join(result, fmt.Errorf("COMPLETION_MISMATCH started=%d completed=%d", r.Started, r.Completed))
	}
	bf, e := os.Create(filepath.Join(output, "block.pprof"))
	if e != nil {
		return r, errors.Join(result, e)
	}
	result = errors.Join(result, pprof.Lookup("block").WriteTo(bf, 0), bf.Close())
	if result == nil {
		r.Status = "pass"
	}
	return r, result
}

func main() {
	scenario := flag.String("scenario", "channel", "cpu, channel, network, backlog")
	output := flag.String("out", "out/channel", "artifact directory")
	failWorker := flag.Bool("fail-worker", false, "close network peer to verify worker error propagation")
	flag.Parse()
	r, e := run(*scenario, *output, *failWorker)
	if e != nil {
		r.Status = "fail"
		r.Error = e.Error()
	}
	b, marshalErr := json.MarshalIndent(r, "", "  ")
	if marshalErr != nil {
		fmt.Fprintln(os.Stderr, marshalErr)
		os.Exit(2)
	}
	if writeErr := os.WriteFile(filepath.Join(*output, "summary.json"), append(b, '\n'), 0600); writeErr != nil {
		fmt.Fprintln(os.Stderr, writeErr)
		os.Exit(2)
	}
	fmt.Println(string(b))
	if e != nil {
		os.Exit(1)
	}
}

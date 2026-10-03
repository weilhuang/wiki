// SPDX-License-Identifier: MIT
package boundaries

import (
	"context"
	"os"
	"sync"
	"sync/atomic"
	"testing"
	"testing/synctest"
)

func TestRoundTrip(t *testing.T) {
	if got := string(RoundTrip()); got != "B42" {
		t.Fatalf("ROUNDTRIP got=%q want=B42", got)
	}
}

func TestUnbufferedReverseEdge(t *testing.T) {
	c := make(chan struct{})
	done := make(chan struct{})
	state := 0
	go func() {
		defer close(done)
		state = 42
		<-c
	}()
	c <- struct{}{}
	if state != 42 {
		t.Fatalf("REVERSE_EDGE got=%d", state)
	}
	<-done
}

func TestCapacityOneSecondSend(t *testing.T) {
	c := make(chan struct{}, 1)
	c <- struct{}{} // S1 occupies the slot; this is not an acknowledgement.
	state := 0
	done := make(chan struct{})
	go func() {
		defer close(done)
		state = 42
		<-c // R1 is synchronized before completion of S2.
	}()
	c <- struct{}{} // S2, with k=1 and C=1.
	if state != 42 {
		t.Fatalf("CAPACITY_EDGE got=%d", state)
	}
	<-c
	<-done
}

func TestCloseDrainsBeforeZero(t *testing.T) {
	c := make(chan int, 1)
	done := make(chan struct{})
	state := 0
	go func() {
		defer close(done)
		c <- 7
		state = 42
		close(c)
	}()
	v, ok := <-c
	if v != 7 || !ok {
		t.Fatalf("DRAIN_FIRST got=(%d,%v)", v, ok)
	}
	// Do not read state yet: receiving the buffered 7 does not imply close.
	v, ok = <-c
	if v != 0 || ok || state != 42 {
		t.Fatalf("CLOSE_EDGE got=(%d,%v) state=%d", v, ok, state)
	}
	<-done
}

func TestPublishedPayload(t *testing.T) {
	original := []byte("A42")
	published := CopyForSend(original)
	if os.Getenv("LAB_VARIANT") == "alias" {
		published = original
	}
	c := make(chan []byte, 1)
	c <- published
	original[0] = 'X' // Ordered mutation: no data race is needed to break isolation.
	got := string(<-c)
	if got != "A42" {
		t.Fatalf("OWNERSHIP_REJECT got=%q want=A42", got)
	}
}

func TestCancellationIsNotJoin(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()
		release := make(chan struct{})
		done := make(chan struct{})
		var exited atomic.Bool
		go func() {
			defer close(done)
			<-ctx.Done()
			<-release // Cleanup is explicitly held; cancellation cannot finish it.
			exited.Store(true)
		}()
		cancel()
		synctest.Wait()
		premature := exited.Load()
		close(release)
		<-done // Always release and join, including the rejected variant.
		if premature || !exited.Load() {
			t.Fatal("CLEANUP_PROTOCOL_BROKEN")
		}
		if os.Getenv("LAB_VARIANT") == "cancel-join" && !premature {
			t.Fatal("CANCEL_JOIN_REJECT cancelled=true exited-at-cancel=false joined-at-end=true")
		}
	})
}

func TestSelectReadySet(t *testing.T) {
	counts := [2]int{}
	for range 128 {
		a, b := make(chan struct{}), make(chan struct{})
		close(a)
		close(b)
		select {
		case <-a:
			counts[0]++
		case <-b:
			counts[1]++
		}
	}
	if counts[0]+counts[1] != 128 {
		t.Fatal("SELECT_ACCOUNTING")
	}
	t.Logf("ready-set samples first=%d second=%d; no fairness assertion", counts[0], counts[1])
}

func TestRaceFixture(t *testing.T) {
	if os.Getenv("LAB_VARIANT") != "race" {
		t.Skip("deliberate race runs separately")
	}
	start := make(chan struct{})
	var wg sync.WaitGroup
	var x int
	for i := range 2 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			for range 10000 {
				x = i
			}
		}()
	}
	close(start)
	wg.Wait()
	t.Logf("RACE_FIXTURE_JOINED final=%d", x)
}

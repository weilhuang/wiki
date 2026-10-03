// SPDX-License-Identifier: MIT
package boundaries

// CopyForSend establishes an independent backing array before publication.
func CopyForSend(src []byte) []byte {
	return append([]byte(nil), src...)
}

// RoundTrip transfers ownership to a worker, then waits for it to return.
// Only the current owner accesses the backing array. Both workers are joined.
func RoundTrip() []byte {
	in := make(chan []byte, 1)
	out := make(chan []byte, 1)
	done := make(chan struct{})
	go func() {
		defer close(done)
		buf := <-in
		buf[0] = 'B'
		out <- buf
	}()
	buf := []byte("A42")
	in <- buf
	buf = nil // A convention: Go does not invalidate other aliases.
	buf = <-out
	<-done
	return buf
}

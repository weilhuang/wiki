//go:build integration

package tests

import (
	"errors"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	mysql "github.com/go-sql-driver/mysql"
)

// commitProxy forwards real MySQL packets and drops exactly the successful
// COMMIT response. It does not emulate a database or decode credentials.
type commitProxy struct {
	DSN         string
	Dropped     chan struct{}
	listener    net.Listener
	mu          sync.Mutex
	connections []net.Conn
	wg          sync.WaitGroup
	cut         atomic.Bool
	closing     atomic.Bool
}

func newCommitProxy(t *testing.T, dsn string) *commitProxy {
	t.Helper()
	cfg, err := mysql.ParseDSN(dsn)
	must(t, err, "proxy configuration")
	if cfg.Net != "tcp" {
		t.Fatal("proxy requires loopback TCP MySQL")
	}
	target := cfg.Addr
	host, _, err := net.SplitHostPort(target)
	must(t, err, "proxy target")
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		t.Fatal("proxy target must be loopback")
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	must(t, err, "proxy listen")
	p := &commitProxy{Dropped: make(chan struct{}), listener: listener}
	cfg.Addr = listener.Addr().String()
	cfg.TLSConfig = "false"
	p.DSN = cfg.FormatDSN()
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		for {
			client, e := listener.Accept()
			if e != nil {
				return
			}
			upstream, e := net.DialTimeout("tcp", target, time.Second)
			if e != nil {
				_ = client.Close()
				continue
			}
			p.mu.Lock()
			p.connections = append(p.connections, client, upstream)
			if p.closing.Load() {
				_ = client.Close()
				_ = upstream.Close()
				p.mu.Unlock()
				return
			}
			p.mu.Unlock()
			p.wg.Add(1)
			go p.session(client, upstream)
		}
	}()
	return p
}
func packet(c net.Conn) ([]byte, error) {
	h := make([]byte, 4)
	if _, err := io.ReadFull(c, h); err != nil {
		return nil, err
	}
	n := int(h[0]) | int(h[1])<<8 | int(h[2])<<16
	if n > 1<<20 {
		return nil, errors.New("bounded proxy packet limit")
	}
	body := make([]byte, n)
	if _, err := io.ReadFull(c, body); err != nil {
		return nil, err
	}
	return append(h, body...), nil
}
func sendPacket(c net.Conn, b []byte) error {
	for len(b) > 0 {
		n, err := c.Write(b)
		if err != nil {
			return err
		}
		if n == 0 {
			return io.ErrShortWrite
		}
		b = b[n:]
	}
	return nil
}
func (p *commitProxy) session(client, server net.Conn) {
	defer p.wg.Done()
	defer client.Close()
	defer server.Close()
	_ = client.SetDeadline(time.Now().Add(5 * time.Second))
	_ = server.SetDeadline(time.Now().Add(5 * time.Second))
	var commit atomic.Bool
	upDone := make(chan struct{})
	go func() {
		defer close(upDone)
		defer server.Close()
		for {
			b, e := packet(client)
			if e != nil {
				return
			}
			if len(b) > 5 && b[4] == 3 && strings.EqualFold(strings.TrimSpace(string(b[5:])), "commit") {
				commit.Store(true)
			}
			if sendPacket(server, b) != nil {
				return
			}
		}
	}()
	for {
		b, e := packet(server)
		if e != nil {
			break
		}
		if commit.Swap(false) && len(b) > 4 && b[4] == 0 && p.cut.CompareAndSwap(false, true) {
			close(p.Dropped)
			break
		}
		if sendPacket(client, b) != nil {
			break
		}
	}
	_ = client.Close()
	_ = server.Close()
	<-upDone
}
func (p *commitProxy) Close() {
	p.closing.Store(true)
	_ = p.listener.Close()
	p.mu.Lock()
	for _, c := range p.connections {
		_ = c.Close()
	}
	p.mu.Unlock()
	p.wg.Wait()
}

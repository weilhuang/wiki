package runtime

import (
	"context"
	"database/sql"
	"errors"
	"net"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	pb "example.com/reservation-service/api/reservation/v1"
	"example.com/reservation-service/internal/domain"
	"example.com/reservation-service/internal/grpcapi"
	"example.com/reservation-service/internal/httpapi"
	"google.golang.org/grpc"
)

type Runtime struct {
	DB            *sql.DB
	HTTP          *http.Server
	GRPC          *grpc.Server
	HTTPListener  net.Listener
	GRPCListener  net.Listener
	Errors        chan error
	ready         atomic.Bool
	serve         sync.WaitGroup
	stopped       chan struct{}
	once          sync.Once
	shutdownError error
}

func New(db *sql.DB, service *domain.Service) *Runtime {
	r := &Runtime{DB: db, Errors: make(chan error, 2), stopped: make(chan struct{})}
	a := &httpapi.API{Service: service, Tokens: domain.TeachingTokens(), Ready: func(ctx context.Context) bool { return r.ready.Load() && db.PingContext(ctx) == nil }}
	r.HTTP = &http.Server{Handler: a.Handler(), ReadHeaderTimeout: time.Second, ReadTimeout: 3 * time.Second, WriteTimeout: 4 * time.Second, IdleTimeout: 15 * time.Second, MaxHeaderBytes: 4096}
	r.GRPC = grpc.NewServer(grpc.MaxRecvMsgSize(2048), grpc.MaxSendMsgSize(2048), grpc.MaxConcurrentStreams(16))
	pb.RegisterReservationServiceServer(r.GRPC, &grpcapi.API{Service: service, Tokens: domain.TeachingTokens()})
	return r
}
func (r *Runtime) Start(httpListener, grpcListener net.Listener) {
	r.HTTPListener = httpListener
	r.GRPCListener = grpcListener
	r.ready.Store(true)
	r.serve.Add(2)
	go func() {
		defer r.serve.Done()
		err := r.HTTP.Serve(httpListener)
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			r.Errors <- errors.New("http serve failed")
		}
	}()
	go func() {
		defer r.serve.Done()
		err := r.GRPC.Serve(grpcListener)
		if err != nil && !errors.Is(err, grpc.ErrServerStopped) {
			r.Errors <- errors.New("grpc serve failed")
		}
	}()
}
func (r *Runtime) Stopped() <-chan struct{} { return r.stopped }
func (r *Runtime) Shutdown(ctx context.Context) error {
	r.once.Do(func() {
		defer close(r.stopped)
		r.ready.Store(false)
		httpDone := make(chan error, 1)
		grpcDone := make(chan struct{})
		go func() { httpDone <- r.HTTP.Shutdown(ctx) }()
		go func() { r.GRPC.GracefulStop(); close(grpcDone) }()
		select {
		case <-grpcDone:
		case <-ctx.Done():
			r.GRPC.Stop()
			<-grpcDone
			r.shutdownError = ctx.Err()
		}
		if err := <-httpDone; err != nil {
			r.shutdownError = err
			_ = r.HTTP.Close()
		}
		r.serve.Wait()
		if err := r.DB.Close(); err != nil && r.shutdownError == nil {
			r.shutdownError = err
		}
	})
	<-r.stopped
	return r.shutdownError
}

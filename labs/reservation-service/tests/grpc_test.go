//go:build integration

package tests

import (
	"context"
	"errors"
	"io"
	"net"
	"sync/atomic"
	"testing"
	"time"

	pb "example.com/reservation-service/api/reservation/v1"
	"example.com/reservation-service/internal/domain"
	"example.com/reservation-service/internal/grpcapi"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
)

func rpcContext(token string) context.Context {
	if token == "" {
		return context.Background()
	}
	return metadata.NewOutgoingContext(context.Background(), metadata.Pairs("authorization", token))
}
func rpcFor(f *fixture, api *grpcapi.API) pb.ReservationServiceClient {
	if api == nil {
		api = &grpcapi.API{Service: f.service, Tokens: domain.TeachingTokens()}
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	must(f.t, err, "grpc listen")
	server := grpc.NewServer(grpc.MaxRecvMsgSize(2048), grpc.MaxSendMsgSize(2048), grpc.MaxConcurrentStreams(16))
	pb.RegisterReservationServiceServer(server, api)
	done := make(chan error, 1)
	go func() { done <- server.Serve(listener) }()
	conn, err := grpc.NewClient(listener.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	must(f.t, err, "grpc client")
	f.t.Cleanup(func() {
		must(f.t, conn.Close(), "grpc client close")
		server.Stop()
		err := <-done
		if err != nil && !errors.Is(err, grpc.ErrServerStopped) {
			f.t.Fatal("grpc serve result")
		}
	})
	return pb.NewReservationServiceClient(conn)
}
func rpcInput(id string) *pb.ReserveRequest {
	return &pb.ReserveRequest{OperationId: id, Sku: "book", Quantity: 1}
}
func rpcError(t *testing.T, err error, want codes.Code, code string) {
	t.Helper()
	if err == nil {
		t.Fatal("GRPC_EXPECTED_ERROR")
	}
	s := status.Convert(err)
	equal(t, s.Code(), want, "GRPC_STATUS")
	equal(t, s.Message(), code, "GRPC_MESSAGE")
	details := s.Details()
	equal(t, len(details), 1, "GRPC_DETAILS_COUNT")
	d, ok := details[0].(*pb.PublicError)
	if !ok {
		t.Fatalf("GRPC_DETAIL_TYPE: %T", details[0])
	}
	if !proto.Equal(d, &pb.PublicError{Code: code}) {
		t.Fatal("GRPC_DETAIL_PAYLOAD")
	}
}
func rpcPayload(t *testing.T, got *pb.Operation, id, state string, quantity int64) {
	t.Helper()
	want := &pb.Operation{OperationId: id, Sku: "book", Quantity: quantity, State: state}
	if !proto.Equal(got, want) {
		t.Fatalf("GRPC_PAYLOAD: got %v want %v", got, want)
	}
}
func grpcCases() map[string]func(*fixture) {
	return map[string]func(*fixture){
		"G01": func(f *fixture) {
			h := httpFor(f)
			h.request("POST", "/v1/reservations", good, "Bearer lesson-writer", "application/json", 200, expectedBody("op-a", "confirmed", 1), "CROSS_HTTP")
			client := rpcFor(f, nil)
			op, err := client.Get(rpcContext("Bearer lesson-reader"), &pb.GetRequest{OperationId: "op-a"})
			must(f.t, err, "grpc cross get")
			rpcPayload(f.t, op, "op-a", "confirmed", 1)
			op, err = client.Reserve(rpcContext("Bearer lesson-writer"), rpcInput("op-b"))
			must(f.t, err, "grpc reserve")
			rpcPayload(f.t, op, "op-b", "confirmed", 1)
			h.request("GET", "/v1/reservations/op-b", "", "Bearer lesson-reader", "", 200, expectedBody("op-b", "confirmed", 1), "CROSS_GRPC")
			f.facts(8, 2)
		},
		"G02": func(f *fixture) {
			appEntries, repoEntries := observeEntries(f)
			client := rpcFor(f, nil)
			_, err := client.Reserve(rpcContext(""), rpcInput("op-a"))
			rpcError(f.t, err, codes.Unauthenticated, "unauthenticated")
			equal(f.t, appEntries.Load(), int64(0), "GRPC_AUTH_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(0), "GRPC_AUTH_REPOSITORY")
			f.facts(10, 0)
			_, err = client.Reserve(rpcContext("Bearer bad"), rpcInput("op-a"))
			rpcError(f.t, err, codes.Unauthenticated, "unauthenticated")
			equal(f.t, appEntries.Load(), int64(0), "GRPC_AUTH_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(0), "GRPC_AUTH_REPOSITORY")
			f.facts(10, 0)
			ctx := metadata.NewOutgoingContext(context.Background(), metadata.Pairs("authorization", "Bearer lesson-writer", "authorization", "Bearer lesson-reader"))
			_, err = client.Reserve(ctx, rpcInput("op-a"))
			rpcError(f.t, err, codes.Unauthenticated, "unauthenticated")
			equal(f.t, appEntries.Load(), int64(0), "GRPC_AUTH_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(0), "GRPC_AUTH_REPOSITORY")
			f.facts(10, 0)
			_, err = client.Reserve(rpcContext("Bearer lesson-reader"), rpcInput("op-a"))
			rpcError(f.t, err, codes.PermissionDenied, "permission_denied")
			equal(f.t, appEntries.Load(), int64(0), "GRPC_AUTH_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(0), "GRPC_AUTH_REPOSITORY")
			f.facts(10, 0)
			bad := rpcInput("op-a")
			bad.Quantity = 0
			_, err = client.Reserve(rpcContext("Bearer lesson-writer"), bad)
			rpcError(f.t, err, codes.InvalidArgument, "invalid_argument")
			equal(f.t, appEntries.Load(), int64(1), "GRPC_INVALID_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(0), "GRPC_INVALID_REPOSITORY")
			f.facts(10, 0)
			_, err = client.Get(rpcContext("Bearer lesson-writer"), &pb.GetRequest{OperationId: "absent"})
			rpcError(f.t, err, codes.NotFound, "not_found")
			equal(f.t, appEntries.Load(), int64(2), "GRPC_MISSING_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(1), "GRPC_MISSING_REPOSITORY")
			f.facts(10, 0)
			_, err = client.Reserve(rpcContext("Bearer lesson-writer"), rpcInput("op-a"))
			must(f.t, err, "rpc seed")
			bad.Quantity = 2
			_, err = client.Reserve(rpcContext("Bearer lesson-writer"), bad)
			rpcError(f.t, err, codes.AlreadyExists, "operation_conflict")
			equal(f.t, appEntries.Load(), int64(4), "GRPC_CONFLICT_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(3), "GRPC_CONFLICT_REPOSITORY")
			f.facts(9, 1)
			_, err = f.observer.Exec("UPDATE products SET stock=0")
			must(f.t, err, "stock zero")
			_, err = client.Reserve(rpcContext("Bearer lesson-writer"), rpcInput("op-b"))
			rpcError(f.t, err, codes.FailedPrecondition, "out_of_stock")
			equal(f.t, appEntries.Load(), int64(5), "GRPC_STOCK_ENTRIES")
			equal(f.t, repoEntries.Load(), int64(4), "GRPC_STOCK_REPOSITORY")
			f.facts(0, 2)
			for _, tc := range []struct {
				cause   error
				code    codes.Code
				message string
			}{{errors.New("private sql error"), codes.Internal, "internal"}, {context.Canceled, codes.Canceled, "canceled"}, {context.DeadlineExceeded, codes.DeadlineExceeded, "deadline_exceeded"}, {domain.Fail(domain.OutcomeUnknown, errors.New("private commit error")), codes.Unavailable, "outcome_unknown"}} {
				f.setHooks(func(context.Context, string, int64) error { return tc.cause })
				injectedApp, injectedRepo := observeEntries(f)
				injected := rpcFor(f, nil)
				_, err = injected.Reserve(rpcContext("Bearer lesson-writer"), rpcInput("op-c"))
				rpcError(f.t, err, tc.code, tc.message)
				equal(f.t, injectedApp.Load(), int64(1), "GRPC_MAPPING_ENTRIES")
				equal(f.t, injectedRepo.Load(), int64(1), "GRPC_MAPPING_REPOSITORY")
				f.facts(0, 2)
			}
			f.facts(0, 2)
		},
		"G03": func(f *fixture) {
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
			client := rpcFor(f, nil)
			ctx, cancel := context.WithTimeout(rpcContext("Bearer lesson-writer"), 800*time.Millisecond)
			defer cancel()
			done := make(chan error, 1)
			go func() { _, err := client.Reserve(ctx, rpcInput("op-a")); done <- err }()
			s := <-entered
			f.waitLock(s.id)
			err := <-done
			equal(f.t, status.Code(err), codes.DeadlineExceeded, "GRPC_DEADLINE")
			equal(f.t, status.Convert(err).Message(), "context deadline exceeded", "GRPC_CLIENT_DEADLINE_MESSAGE")
			equal(f.t, len(status.Convert(err).Details()), 0, "GRPC_CLIENT_DEADLINE_DETAILS")
			select {
			case <-s.ctx.Done():
			case <-time.After(time.Second):
				f.t.Fatal("GRPC_SERVER_DEADLINE")
			}
			release()
			f.poolReturned()
			f.facts(10, 0)
		},
		"G04": func(f *fixture) {
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
			client := rpcFor(f, nil)
			ctx, cancel := context.WithCancel(rpcContext("Bearer lesson-writer"))
			defer cancel()
			done := make(chan error, 1)
			go func() { _, err := client.Reserve(ctx, rpcInput("op-a")); done <- err }()
			s := <-entered
			f.waitLock(s.id)
			cancel()
			err := <-done
			equal(f.t, status.Code(err), codes.Canceled, "GRPC_CANCEL")
			equal(f.t, status.Convert(err).Message(), "context canceled", "GRPC_CLIENT_CANCEL_MESSAGE")
			equal(f.t, len(status.Convert(err).Details()), 0, "GRPC_CLIENT_CANCEL_DETAILS")
			select {
			case <-s.ctx.Done():
			case <-time.After(time.Second):
				f.t.Fatal("GRPC_SERVER_CANCEL")
			}
			release()
			f.poolReturned()
			f.facts(10, 0)
		},
		"G05": func(f *fixture) {
			for _, id := range []string{"op-c", "op-a", "op-b"} {
				_, err := f.repo.Reserve(context.Background(), "alice", input(id))
				must(f.t, err, "list seed")
			}
			rejected := input("op-d")
			rejected.Quantity = 100
			_, err := f.repo.Reserve(context.Background(), "alice", rejected)
			must(f.t, err, "rejected list seed")
			_, err = f.repo.Reserve(context.Background(), "bob", input("op-z"))
			must(f.t, err, "other seed")
			client := rpcFor(f, nil)
			stream, err := client.List(rpcContext("Bearer lesson-reader"), &pb.ListRequest{Limit: 2})
			must(f.t, err, "list start")
			for _, id := range []string{"op-a", "op-b"} {
				op, e := stream.Recv()
				must(f.t, e, "stream item")
				rpcPayload(f.t, op, id, "confirmed", 1)
			}
			_, err = stream.Recv()
			equal(f.t, err, io.EOF, "GRPC_STREAM_EOF")
			for _, limit := range []int32{0, 33} {
				s, e := client.List(rpcContext("Bearer lesson-reader"), &pb.ListRequest{Limit: limit})
				must(f.t, e, "invalid list starts")
				_, e = s.Recv()
				rpcError(f.t, e, codes.InvalidArgument, "invalid_argument")
			}
			full, e := client.List(rpcContext("Bearer lesson-reader"), &pb.ListRequest{Limit: 32})
			must(f.t, e, "full list")
			for _, tc := range []struct {
				id, state string
				quantity  int64
			}{{"op-a", "confirmed", 1}, {"op-b", "confirmed", 1}, {"op-c", "confirmed", 1}, {"op-d", "rejected", 100}} {
				op, e := full.Recv()
				must(f.t, e, "full stream item")
				rpcPayload(f.t, op, tc.id, tc.state, tc.quantity)
			}
			_, e = full.Recv()
			equal(f.t, e, io.EOF, "GRPC_FULL_STREAM_EOF")
			f.observe("op-d", "alice", "rejected", 100)
			f.facts(6, 5)
		},
		"G06": func(f *fixture) {
			for _, id := range []string{"op-a", "op-b", "op-c"} {
				_, err := f.repo.Reserve(context.Background(), "alice", input(id))
				must(f.t, err, "slow list seed")
			}
			blocked := make(chan struct{})
			done := make(chan error, 1)
			var attempts atomic.Int64
			api := &grpcapi.API{Service: f.service, Tokens: domain.TeachingTokens(), BeforeSend: func(ctx context.Context, i int) error {
				if i == 1 {
					close(blocked)
					<-ctx.Done()
					return ctx.Err()
				}
				attempts.Add(1)
				return nil
			}, StreamDone: func(err error) { done <- err }}
			client := rpcFor(f, api)
			ctx, cancel := context.WithCancel(rpcContext("Bearer lesson-reader"))
			defer cancel()
			stream, err := client.List(ctx, &pb.ListRequest{Limit: 32})
			must(f.t, err, "slow stream")
			op, err := stream.Recv()
			must(f.t, err, "first item")
			rpcPayload(f.t, op, "op-a", "confirmed", 1)
			<-blocked
			cancel()
			err = <-done
			equal(f.t, status.Code(err), codes.Canceled, "STREAM_SERVER_CANCEL")
			equal(f.t, attempts.Load(), int64(1), "STREAM_BOUNDED_PRODUCER")
			_, err = stream.Recv()
			equal(f.t, status.Code(err), codes.Canceled, "STREAM_CLIENT_CANCEL")
			f.facts(7, 3)
		},
	}
}

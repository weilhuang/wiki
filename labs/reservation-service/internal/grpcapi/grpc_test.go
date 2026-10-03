package grpcapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"testing"

	pb "example.com/reservation-service/api/reservation/v1"
	"example.com/reservation-service/internal/domain"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// This is an adapter unit fixture, not MySQL or network evidence.
type fixedRepository struct{}

func (fixedRepository) Reserve(context.Context, string, domain.Input) (domain.Operation, error) {
	return domain.Operation{}, errors.New("unused")
}
func (fixedRepository) Get(context.Context, string, string) (domain.Operation, error) {
	return domain.Operation{}, errors.New("unused")
}
func (fixedRepository) List(context.Context, string, int) ([]domain.Operation, error) {
	return []domain.Operation{{OperationID: "op-a", SKU: "book", Quantity: 1, State: "confirmed"}, {OperationID: "op-b", SKU: "book", Quantity: 1, State: "confirmed"}}, nil
}

type failedStream struct {
	ctx     context.Context
	failure error
	calls   int
}

func (s *failedStream) Send(*pb.Operation) error     { s.calls++; return s.failure }
func (s *failedStream) Context() context.Context     { return s.ctx }
func (s *failedStream) SetHeader(metadata.MD) error  { return nil }
func (s *failedStream) SendHeader(metadata.MD) error { return nil }
func (s *failedStream) SetTrailer(metadata.MD)       {}
func (s *failedStream) SendMsg(any) error            { return errors.New("unused") }
func (s *failedStream) RecvMsg(any) error            { return errors.New("unused") }
func TestG07StreamSendError(t *testing.T) {
	expected := status.Error(codes.Unavailable, "controlled send failure")
	stream := &failedStream{ctx: metadata.NewIncomingContext(context.Background(), metadata.Pairs("authorization", "Bearer lesson-reader")), failure: expected}
	api := &API{Service: &domain.Service{Repo: fixedRepository{}}, Tokens: domain.TeachingTokens()}
	err := api.List(&pb.ListRequest{Limit: 2}, stream)
	if err != expected || stream.calls != 1 {
		raw, e := json.Marshal(map[string]string{"marker": "STREAM_SEND_ERROR", "got": fmt.Sprintf("err=%v calls=%d", err, stream.calls), "want": "same Send error, calls=1"})
		if e != nil {
			t.Fatal("semantic assertion encoding failed")
		}
		t.Fatalf("SEMANTIC_ASSERT %s", raw)
	}
}

package grpcapi

import (
	"context"
	"time"

	pb "example.com/reservation-service/api/reservation/v1"
	"example.com/reservation-service/internal/domain"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

const Budget = 2 * time.Second

type API struct {
	pb.UnimplementedReservationServiceServer
	Service *domain.Service
	Tokens  map[string]domain.Principal
	// BeforeSend/StreamDone are optional test observation barriers, unset by reservationd.
	BeforeSend func(context.Context, int) error
	StreamDone func(error)
}

func Code(code domain.Code) codes.Code {
	switch code {
	case domain.Unauthenticated:
		return codes.Unauthenticated
	case domain.PermissionDenied:
		return codes.PermissionDenied
	case domain.InvalidArgument:
		return codes.InvalidArgument
	case domain.NotFound:
		return codes.NotFound
	case domain.Conflict:
		return codes.AlreadyExists
	case domain.OutOfStock:
		return codes.FailedPrecondition
	case domain.Canceled:
		return codes.Canceled
	case domain.Deadline:
		return codes.DeadlineExceeded
	case domain.OutcomeUnknown:
		return codes.Unavailable
	default:
		return codes.Internal
	}
}
func Failure(err error) error {
	code := domain.PublicCode(err)
	s := status.New(Code(code), string(code))
	with, e := s.WithDetails(&pb.PublicError{Code: string(code)})
	if e != nil {
		return status.Error(codes.Internal, "internal")
	}
	return with.Err()
}
func (a *API) auth(ctx context.Context, write bool) (domain.Principal, error) {
	md, _ := metadata.FromIncomingContext(ctx)
	v := md.Get("authorization")
	if len(v) != 1 {
		return domain.Principal{}, domain.Fail(domain.Unauthenticated, nil)
	}
	p, ok := a.Tokens[v[0]]
	if !ok {
		return p, domain.Fail(domain.Unauthenticated, nil)
	}
	return p, domain.Authorize(p, write)
}
func payload(op domain.Operation) *pb.Operation {
	return &pb.Operation{OperationId: op.OperationID, Sku: op.SKU, Quantity: op.Quantity, State: op.State}
}
func (a *API) Reserve(ctx context.Context, in *pb.ReserveRequest) (*pb.Operation, error) {
	p, err := a.auth(ctx, true)
	if err != nil {
		return nil, Failure(err)
	}
	ctx, cancel := context.WithTimeout(ctx, Budget)
	defer cancel()
	op, err := a.Service.Reserve(ctx, p, domain.Input{OperationID: in.GetOperationId(), SKU: in.GetSku(), Quantity: in.GetQuantity()})
	if err != nil {
		return nil, Failure(err)
	}
	return payload(op), nil
}
func (a *API) Get(ctx context.Context, in *pb.GetRequest) (*pb.Operation, error) {
	p, err := a.auth(ctx, false)
	if err != nil {
		return nil, Failure(err)
	}
	ctx, cancel := context.WithTimeout(ctx, Budget)
	defer cancel()
	op, err := a.Service.Get(ctx, p, in.GetOperationId())
	if err != nil {
		return nil, Failure(err)
	}
	return payload(op), nil
}
func (a *API) List(in *pb.ListRequest, stream grpc.ServerStreamingServer[pb.Operation]) (err error) {
	defer func() {
		if a.StreamDone != nil {
			a.StreamDone(err)
		}
	}()
	p, err := a.auth(stream.Context(), false)
	if err != nil {
		return Failure(err)
	}
	ctx, cancel := context.WithTimeout(stream.Context(), Budget)
	defer cancel()
	ops, err := a.Service.List(ctx, p, int(in.GetLimit()))
	if err != nil {
		return Failure(err)
	}
	for i, op := range ops {
		if a.BeforeSend != nil {
			if err = a.BeforeSend(ctx, i); err != nil {
				return Failure(err)
			}
		}
		if err = ctx.Err(); err != nil {
			return Failure(err)
		}
		if err = stream.Send(payload(op)); err != nil {
			return err
		}
	}
	return nil
}

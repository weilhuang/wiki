package domain

import (
	"context"
	"errors"
	"regexp"
)

type Code string

const (
	Unauthenticated  Code = "unauthenticated"
	PermissionDenied Code = "permission_denied"
	InvalidArgument  Code = "invalid_argument"
	NotFound         Code = "not_found"
	Conflict         Code = "operation_conflict"
	OutOfStock       Code = "out_of_stock"
	Canceled         Code = "canceled"
	Deadline         Code = "deadline_exceeded"
	OutcomeUnknown   Code = "outcome_unknown"
	Internal         Code = "internal"
)

type Failure struct {
	Code  Code
	Cause error
}

func (e *Failure) Error() string        { return string(e.Code) }
func (e *Failure) Unwrap() error        { return e.Cause }
func Fail(code Code, cause error) error { return &Failure{Code: code, Cause: cause} }
func PublicCode(err error) Code {
	var e *Failure
	if errors.As(err, &e) {
		return e.Code
	}
	if errors.Is(err, context.Canceled) {
		return Canceled
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return Deadline
	}
	return Internal
}

type Principal struct {
	Subject string
	Reserve bool
	Read    bool
}

func Authorize(p Principal, write bool) error {
	if p.Subject == "" {
		return Fail(Unauthenticated, nil)
	}
	if (write && !p.Reserve) || (!write && !p.Read) {
		return Fail(PermissionDenied, nil)
	}
	return nil
}

// TeachingTokens are public lesson markers, not production credentials.
func TeachingTokens() map[string]Principal {
	return map[string]Principal{
		"Bearer lesson-writer": {Subject: "alice", Reserve: true, Read: true},
		"Bearer lesson-reader": {Subject: "alice", Read: true},
		"Bearer lesson-other":  {Subject: "bob", Reserve: true, Read: true},
	}
}

type Input struct {
	OperationID string `json:"operation_id"`
	SKU         string `json:"sku"`
	Quantity    int64  `json:"quantity"`
}
type Operation struct {
	OperationID string `json:"operation_id"`
	SKU         string `json:"sku"`
	Quantity    int64  `json:"quantity"`
	State       string `json:"state"`
}

func (o Operation) Same(in Input) bool {
	return o.OperationID == in.OperationID && o.SKU == in.SKU && o.Quantity == in.Quantity
}

var identifier = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,47}$`)

func ValidID(s string) bool { return identifier.MatchString(s) }
func Validate(in Input) error {
	if !ValidID(in.OperationID) || !ValidID(in.SKU) || in.Quantity < 1 || in.Quantity > 100 {
		return Fail(InvalidArgument, nil)
	}
	return nil
}

type Repository interface {
	Reserve(context.Context, string, Input) (Operation, error)
	Get(context.Context, string, string) (Operation, error)
	List(context.Context, string, int) ([]Operation, error)
}
type Service struct {
	Repo    Repository
	OnEntry func(string)
}

func (s *Service) enter(method string) {
	if s.OnEntry != nil {
		s.OnEntry(method)
	}
}
func (s *Service) Reserve(ctx context.Context, p Principal, in Input) (Operation, error) {
	if err := Authorize(p, true); err != nil {
		return Operation{}, err
	}
	s.enter("reserve")
	if err := Validate(in); err != nil {
		return Operation{}, err
	}
	op, err := s.Repo.Reserve(ctx, p.Subject, in)
	if err != nil {
		return Operation{}, err
	}
	if op.State == "rejected" {
		return op, Fail(OutOfStock, nil)
	}
	if op.State != "confirmed" {
		return Operation{}, Fail(Internal, nil)
	}
	return op, nil
}
func (s *Service) Get(ctx context.Context, p Principal, id string) (Operation, error) {
	if err := Authorize(p, false); err != nil {
		return Operation{}, err
	}
	s.enter("get")
	if !ValidID(id) {
		return Operation{}, Fail(InvalidArgument, nil)
	}
	return s.Repo.Get(ctx, p.Subject, id)
}
func (s *Service) List(ctx context.Context, p Principal, limit int) ([]Operation, error) {
	if err := Authorize(p, false); err != nil {
		return nil, err
	}
	s.enter("list")
	if limit < 1 || limit > 32 {
		return nil, Fail(InvalidArgument, nil)
	}
	return s.Repo.List(ctx, p.Subject, limit)
}

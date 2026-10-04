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

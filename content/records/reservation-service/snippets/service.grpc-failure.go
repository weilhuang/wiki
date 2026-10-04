func Failure(err error) error {
	code := domain.PublicCode(err)
	s := status.New(Code(code), string(code))
	with, e := s.WithDetails(&pb.PublicError{Code: string(code)})
	if e != nil {
		return status.Error(codes.Internal, "internal")
	}
	return with.Err()
}

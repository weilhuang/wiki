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

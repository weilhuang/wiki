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

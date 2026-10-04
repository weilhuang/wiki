	body, err := io.ReadAll(http.MaxBytesReader(c.Writer, c.Request.Body, MaxBody))
	if err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			writeError(c, 413, "body_too_large")
		} else {
			writeError(c, 400, "body_read_failed")
		}
		return
	}
	in, err := Decode(body)
	if err != nil {
		writeError(c, 400, "invalid_json")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), Budget)
	defer cancel()

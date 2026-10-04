func Decode(body []byte) (in domain.Input, err error) {
	invalid := errors.New("invalid JSON contract")
	d := json.NewDecoder(bytes.NewReader(body))
	token, err := d.Token()
	if err != nil || token != json.Delim('{') {
		return in, invalid
	}
	fields := map[string]json.RawMessage{}
	for d.More() {
		token, err = d.Token()
		if err != nil {
			return in, invalid
		}
		key, ok := token.(string)
		if !ok {
			return in, invalid
		}
		if key != "operation_id" && key != "sku" && key != "quantity" {
			return in, invalid
		}
		if _, exists := fields[key]; exists {
			return in, invalid
		}
		var raw json.RawMessage
		if err = d.Decode(&raw); err != nil || bytes.Equal(raw, []byte("null")) {
			return in, invalid
		}
		fields[key] = raw
	}
	token, err = d.Token()
	if err != nil || token != json.Delim('}') || len(fields) != 3 {
		return in, invalid
	}
	if _, err = d.Token(); err != io.EOF {
		return in, invalid
	}
	if json.Unmarshal(fields["operation_id"], &in.OperationID) != nil || json.Unmarshal(fields["sku"], &in.SKU) != nil || json.Unmarshal(fields["quantity"], &in.Quantity) != nil {
		return in, invalid
	}
	return in, nil
}

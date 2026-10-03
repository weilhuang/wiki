package main

import (
	"errors"
	"fmt"
	"io"
	"os"

	corelab "example.com/go-core-engineering-lab"
)

func main() { writeDemo(os.Stdout) }

func writeDemo(w io.Writer) {
	in := corelab.Snapshot{Name: "demo", Chunks: [][]byte{[]byte("A42")}}
	out := corelab.CloneSnapshot(in)
	in.Chunks[0][0] = 'X'
	fmt.Fprintf(w, "input=%s snapshot=%s\n", in.Chunks[0], out.Chunks[0])
	_, err := corelab.Load("Bad/key")
	status, body := corelab.ErrorResponse(err)
	var field *corelab.FieldError
	fmt.Fprintf(w, "invalid=%t field=%t status=%d code=%s\n", errors.Is(err, corelab.ErrInvalid), errors.As(err, &field), status, body.Code)
}

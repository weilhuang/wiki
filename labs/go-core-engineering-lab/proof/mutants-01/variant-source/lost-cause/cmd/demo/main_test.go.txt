package main

import (
	"bytes"
	"testing"
)

func TestDemoOutput(t *testing.T) {
	var output bytes.Buffer
	writeDemo(&output)
	want := "input=X42 snapshot=A42\ninvalid=true field=true status=400 code=invalid_argument\n"
	if output.String() != want {
		t.Fatalf("CONTRACT[demo-output] got=%q want=%q", output.String(), want)
	}
}

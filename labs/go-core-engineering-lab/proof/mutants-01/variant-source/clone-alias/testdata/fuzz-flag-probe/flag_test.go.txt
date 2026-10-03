package flagprobe

import (
	"flag"
	"testing"
)

var wantMinimize = flag.String("want-minimize", "", "required normalized testing flag value")

// This observes the real testing package's parsed flag, not a copied parser.
// It does not claim to observe worker minimization; the pinned source chain
// separately establishes how these values control coordinator dispatch.
func TestFuzzMinimizationFlagParsing(t *testing.T) {
	parsed := flag.Lookup("test.fuzzminimizetime")
	if parsed == nil || *wantMinimize == "" {
		t.Fatal("CONTRACT[fuzz-min-flag] parsed flag and explicit expectation are required")
	}
	got := parsed.Value.String()
	if got != *wantMinimize {
		t.Fatalf("CONTRACT[fuzz-min-flag] got=%q want=%q", got, *wantMinimize)
	}
	t.Logf("FUZZ_MIN_FLAG=%s", got)
}

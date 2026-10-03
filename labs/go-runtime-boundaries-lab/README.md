# Go channel and runtime boundaries lab

Go 1.27.1, Linux amd64; only the Go standard library and Python 3 standard library are required. No external Go modules, Docker, persistent server or HTTP profiling endpoint. Teaching code is MIT licensed; pinned Go source snapshots retain the Go BSD license in sources/LICENSE.

## Read before running

- ownership.go / ownership_test.go explain publication, independent copies, ownership return, capacity and close edges, select readiness and cancellation versus join
- cmd/diagnose/main.go creates four separate finite experiments: cpu, channel, network, backlog
- The network case uses a temporary loopback listener and a single TCP connection pair. The listener closes after accept; both connections have a 2-second deadline and close after worker completion
- Backlog input is fixed at 24 workers, permits=2; it is a bounded demonstration of accumulation outside the permits, not an infinite stress test
- CPU uses one worker and a 450 ms sampling window. Profile and trace introduce runtime helper goroutines separately from the application worker limits
- run.py enforces per-command timeouts and a total budget. Each subprocess has its own process group and is killed as a group on timeout. Failed stages remain failed; a missing target profile never becomes a fabricated observation

Use a machine where you have permission to compile and make loopback connections. In a shared workspace, obtain its coordinator's resource slot first. Select an already installed Go 1.27.1 toolchain; do not silently download a newer toolchain or dependencies. A shared cache may be passed using --cache. This module has no dependency lock beyond the exact go.mod toolchain requirement because it has no external modules.

## Full bounded run

Set your shell PATH to the installed Go 1.27.1 executable. Run from this directory:

```sh
go version
timeout --signal=TERM --kill-after=5s 180s python3 run.py --private ./private-run --seconds 170
```

`private-run/` receives binaries, raw profiles, traces and raw logs. It must not be published. `proof/` is the sanitized text output and source/command record. In recorded commands, PRIVATE denotes the chosen private output directory and GO_TOOLCHAIN replaces the toolchain root. No private absolute path is needed to repeat the steps. This command replaces proof with the new run's observations; first preserve an existing result if it is evidence you need to keep. Public artifacts were generated with an explicitly selected existing Go executable and cache, and a 90-second outer / 80-second inner budget for the second attempt. Reproduction may need more cold-cache time; exceeding the budget is a failure, not success.

The runner uses GOMAXPROCS=2, GOTOOLCHAIN=local, GOWORK=off, GOENV=off, GOPROXY=off, GOSUMDB=off and -p=1. It never dumps your environment. Builds set -buildvcs=false and -trimpath because this standalone teaching package does not stamp an unrelated ancestor checkout and should not embed its absolute paths.

Representative commands, already executed by the runner:

```sh
go test -p=1 -count=1 -v -timeout=20s ./...
go test -p=1 -race -count=1 -v -timeout=20s ./...
go vet -p=1 ./...
go build -p=1 -buildvcs=false -trimpath -o private-run/diagnose ./cmd/diagnose
private-run/diagnose -scenario network -out private-run/network
go tool pprof -top private-run/network/cpu.pprof
go tool trace -pprof=net private-run/network/trace.out > private-run/network/net.pprof
go tool pprof -top private-run/network/net.pprof
```

The normal tests skip the deliberate race fixture. `LAB_VARIANT=alias` selects a wrong publication implementation; `LAB_VARIANT=cancel-join` tests a deliberately false cancellation-as-join assertion. The runner accepts their exit=1 only when the specific test and rejection marker are present; compiler errors, wrong tests and timeouts are rejected as evidence. `LAB_VARIANT=race` runs an actual two-worker race and must produce a race detector report. No race report on the normal paths is not a proof of general race freedom.

The independent network failure case closes its peer after confirmed IO wait. Its expected output has WORKER_ERROR: EOF, started=joined=1, completed=0, status=fail and exit=1. This prevents a worker's error from being swallowed by a successful main process.

## Saved evidence

- proof/commands.json: 26 executed stages from the second attempt, with exit status, timeout flag and duration
- proof/input-source-hashes.json: exact input source bytes for that run
- proof/result.json: result summary and limits
- proof/*-goroutines.txt: snapshots with trimmed source locations
- proof/*-cpu-top.txt, *-block-top.txt, *-trace-top.txt: real pprof outputs, not expected-output templates
- proof/*-raw-artifact-hashes.json: identity and sizes of private original profiles and traces
- attempts/attempt-1/: earlier exact source snapshot, commands and VCS stamping failure. Diagnostics did not start in that attempt. Source copies use .txt suffixes so they cannot accidentally join `go test ./...`
- source-review.json: pinned upstream files fetched from go1.27.1 and byte comparison with the installed release's corresponding files

There is no performance ranking, production capacity estimate, fairness proof, full netpoll verification, external network test, HTTP load test, cgo test, disk IO test or container CPU scheduling test. CPU samples, aggregate blocking delays and wall-clock request latency measure different things.

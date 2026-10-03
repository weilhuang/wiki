#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export GOMAXPROCS=2
export GOFLAGS='-p=1 -mod=readonly -buildvcs=false'
export GOMEMLIMIT=768MiB
export GOTOOLCHAIN=local
[ "$(go env GOVERSION)" = go1.27.1 ] || { echo 'Go 1.27.1 required' >&2; exit 1; }
case "${1:-build}" in
  build)
    mkdir -p out
    go build -tags=nomsgpack -o out/reservationd ./cmd/reservationd
    ;;
  migrate)
    : "${MYSQL_DSN:?Set MYSQL_DSN for your own empty teaching schema}"
    exec ./out/reservationd -migrate
    ;;
  serve)
    : "${MYSQL_DSN:?Set MYSQL_DSN for your own teaching schema}"
    exec ./out/reservationd
    ;;
  unit)
    go test -tags=nomsgpack -count=1 -timeout=20s ./internal/grpcapi
    ;;
  integration)
    : "${RESERVATION_MYSQL_ADMIN_DSN:?Set a disposable MySQL admin connection}"
    : "${RESERVATION_BIN:?Set an absolute path to the built reservationd}"
    go test -tags=integration,nomsgpack -count=1 -timeout=90s ./tests
    ;;
  *) echo 'expected build, migrate, serve, unit, or integration' >&2; exit 2 ;;
esac

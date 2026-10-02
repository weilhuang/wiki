#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${JAVA_HOME:?请将 JAVA_HOME 指向 JDK 21；运行不会下载或安装工具链}"
MODE="${1:-api}"
OUT="${2:-$PWD/.run}"
case "$MODE" in api|impl|verify) ;; *) printf 'Usage: ./run.sh [api|impl|verify] [output-directory]\n' >&2; exit 2;; esac
mkdir -p "$OUT/classes"
JAVA="$JAVA_HOME/bin/java"
JAVAC="$JAVA_HOME/bin/javac"
"$JAVA" -version > "$OUT/java-version.txt" 2>&1
"$JAVAC" -version > "$OUT/javac-version.txt" 2>&1
grep -Eq '^javac 21([. ]|$)' "$OUT/javac-version.txt" || { echo '需要 JDK 21' >&2; exit 2; }
"$JAVAC" -J-Xmx96m -encoding UTF-8 --release 21 -d "$OUT/classes" src/HashMapWalkthrough.java src/HashMapLab.java
RUN=("$JAVA" -Xms16m -Xmx64m -XX:ActiveProcessorCount=1 -cp "$OUT/classes")
"${RUN[@]}" HashMapWalkthrough > "$OUT/walkthrough.txt"
diff -u expected-walkthrough.txt "$OUT/walkthrough.txt"
"${RUN[@]}" HashMapLab --api | tee "$OUT/api.txt"
diff -u expected-api.txt "$OUT/api.txt"
if [[ "$MODE" == impl || "$MODE" == verify ]]; then
  "${RUN[@]}" HashMapLab --impl | tee "$OUT/implementation.txt"
  diff -u expected-implementation.txt "$OUT/implementation.txt"
fi
if [[ "$MODE" == verify ]]; then
  : > "$OUT/negative-summary.txt"
  for hypothesis in equal-adds collision-overwrites mutable-stays-readable eighth-put-tree resize-keeps-every-index; do
    set +e
    "${RUN[@]}" HashMapLab --negative "$hypothesis" > "$OUT/negative-$hypothesis.txt" 2>&1
    code=$?
    set -e
    # 只接受主异常首行为目标 AssertionError；其他异常即使带同一文本也必须拒绝。
    IFS= read -r exception_header < "$OUT/negative-$hypothesis.txt" || exception_header=""
    expected_header="Exception in thread \"main\" java.lang.AssertionError: ASSERTION_FAILED: wrong hypothesis $hypothesis"
    if [[ "$code" != 1 ]] || [[ "$exception_header" != "$expected_header" && "$exception_header" != "$expected_header expected="* ]]; then
      echo "反向断言未按预期失败: $hypothesis exit=$code" >&2
      printf '实际主异常: %s\n' "$exception_header" >&2
      exit 1
    fi
    printf 'EXPECTED_FAILURE %s exit=%s\n' "$hypothesis" "$code" | tee -a "$OUT/negative-summary.txt"
  done
fi
printf 'PASS runner mode=%s\n' "$MODE"

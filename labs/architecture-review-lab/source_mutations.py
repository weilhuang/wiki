"""Apply only the three bundled review patches to an in-memory source copy."""
from pathlib import Path
import re

PATCHES = {"async-abort-only-half-commit", "revoked-replay-only-side-effect",
           "completed-outbox-rollback"}


def apply_patch(source, patch):
    original = source.splitlines(keepends=True)
    lines = patch.splitlines(keepends=True)
    if lines[:2] != ["--- a/review_model.py\n", "+++ b/review_model.py\n"]:
        raise ValueError("unexpected patch target")
    output, cursor, i = [], 0, 2
    while i < len(lines):
        match = re.fullmatch(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n", lines[i])
        if not match:
            raise ValueError("invalid patch header")
        start, old_count, _, new_count = map(int, match.groups())
        i += 1
        old, new = [], []
        while i < len(lines) and not lines[i].startswith("@@ "):
            prefix, body = lines[i][0], lines[i][1:]
            if prefix not in " +-":
                raise ValueError("unsupported patch syntax")
            if prefix in " -":
                old.append(body)
            if prefix in " +":
                new.append(body)
            i += 1
        offset = start - 1
        if len(old) != old_count or len(new) != new_count or offset < cursor:
            raise ValueError("patch range mismatch")
        if original[offset:offset + old_count] != old:
            raise ValueError("patch context mismatch")
        output.extend(original[cursor:offset])
        output.extend(new)
        cursor = offset + old_count
    output.extend(original[cursor:])
    return "".join(output)


def mutated_model(name):
    if name not in PATCHES:
        raise ValueError("unknown reviewed source mutation")
    root = Path(__file__).resolve().parent
    source = (root / "review_model.py").read_text()
    patch = (root / "review_regressions" / (name + ".patch")).read_text()
    altered = apply_patch(source, patch)
    if altered == source:
        raise ValueError("patch made no change")
    namespace = {"__name__": "review_mutant_" + name.replace("-", "_")}
    exec(compile(altered, "<review-mutant:" + name + ">", "exec"), namespace)
    return namespace["ReviewModel"]

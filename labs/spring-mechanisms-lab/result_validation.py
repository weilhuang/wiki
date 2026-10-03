"""Classify a completed process without confusing failures with counterexamples."""
def validate_result(exit_code, text, expected_exit=0, assertion=None, marker=None,
                    timed_out=False, cleanup_error=None):
    if timed_out or cleanup_error is not None:
        raise AssertionError('timeout or cleanup failure')
    if exit_code != expected_exit:
        raise AssertionError('unexpected process exit')
    uncaught = [line for line in text.splitlines() if line.startswith('Exception in thread "')]
    if assertion is not None:
        expected = 'Exception in thread "main" java.lang.AssertionError: ' + assertion
        if uncaught != [expected]:
            raise AssertionError('not the sole expected main-thread AssertionError')
    elif uncaught:
        raise AssertionError('uncaught thread failure on nominal success path')
    if marker is not None and marker not in text.splitlines():
        raise AssertionError('missing completion marker')

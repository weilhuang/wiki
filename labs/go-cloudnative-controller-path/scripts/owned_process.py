"""Terminate only the subprocess session created by this lab and verify it is gone."""
import os
import signal
import subprocess
import time


def group_exists(group):
    try: os.killpg(group, 0)
    except ProcessLookupError: return False
    return True


def finish_group(process, seconds=2):
    deadline = time.monotonic()+seconds
    row = {'owned_process_group':process.pid, 'process_group_cleanup':False,
           'lingering_children':False, 'termination_sent':False, 'parent_reaped':False}
    # The caller created start_new_session=True; its PID is exactly the owned PGID.
    alive = group_exists(process.pid)
    row['lingering_children'] = alive and process.poll() is not None
    if alive:
        try: os.killpg(process.pid, signal.SIGKILL); row['termination_sent']=True
        except ProcessLookupError: pass
    try:
        process.wait(timeout=max(.01,deadline-time.monotonic()))
        row['parent_reaped']=True
    except subprocess.TimeoutExpired:
        return row
    while group_exists(process.pid) and time.monotonic()<deadline:
        time.sleep(min(.02,max(0,deadline-time.monotonic())))
    row['process_group_cleanup']=not group_exists(process.pid)
    return row

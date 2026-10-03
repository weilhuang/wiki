#!/usr/bin/env python3
"""Wall-clock phase deadlines and separately reserved evidence capacity."""
import time

WRAPPER_SECONDS=650  # external timeout 655s plus at most 5s termination = 660s
CLEANUP_SECONDS=90
FINAL_SECONDS=15
SAFETY_SECONDS=15
COLLECT_SECONDS=60
UPLOAD_SECONDS=120
JOB_MARGIN_SECONDS=120
JOB_SECONDS=1500
NORMAL_BYTES=24*1024*1024
RESERVED_BYTES=8*1024*1024

class Deadlines:
 def __init__(self,job_started,wall_now=None,monotonic_now=None):
  wall_now=time.time() if wall_now is None else wall_now
  monotonic_now=time.monotonic() if monotonic_now is None else monotonic_now
  if not isinstance(job_started,int) or job_started>wall_now or wall_now-job_started>JOB_SECONDS:raise ValueError('invalid whole-job start time')
  available=min(WRAPPER_SECONDS,JOB_SECONDS-(wall_now-job_started)-COLLECT_SECONDS-UPLOAD_SECONDS-JOB_MARGIN_SECONDS)
  if available<=CLEANUP_SECONDS+FINAL_SECONDS+SAFETY_SECONDS:raise ValueError('insufficient job budget for bounded work and cleanup')
  self.started=monotonic_now
  self.wrapper=monotonic_now+available
  self.final=self.wrapper-SAFETY_SECONDS
  self.cleanup=self.final-FINAL_SECONDS
  self.work=self.cleanup-CLEANUP_SECONDS
 def command(self,timeout,cleanup=False,now=None):
  now=time.monotonic() if now is None else now
  # capture may spend at most two more seconds terminating its process group.
  remaining=(self.cleanup if cleanup else self.work)-now-2
  if remaining<=0:raise TimeoutError('phase deadline exhausted')
  return min(timeout,remaining)

class EvidenceBudget:
 def __init__(self):self.raw=0;self.public=0;self.normal_raw=0;self.normal_public=0;self.reserved_raw=0;self.reserved_public=0
 def remaining(self,reserved=False):
  cap=RESERVED_BYTES if reserved else NORMAL_BYTES
  used=self.reserved_raw if reserved else self.normal_raw
  public_used=self.reserved_public if reserved else self.normal_public
  return max(0,min(cap-used,cap-public_used,NORMAL_BYTES+RESERVED_BYTES-self.raw,NORMAL_BYTES+RESERVED_BYTES-self.public))
 def add(self,raw,public,reserved=False):
  cap=RESERVED_BYTES if reserved else NORMAL_BYTES
  a=self.reserved_raw if reserved else self.normal_raw;b=self.reserved_public if reserved else self.normal_public
  if raw<0 or public<0 or a+raw>cap or b+public>cap or self.raw+raw>NORMAL_BYTES+RESERVED_BYTES or self.public+public>NORMAL_BYTES+RESERVED_BYTES:raise ValueError('evidence phase budget exhausted')
  self.raw+=raw;self.public+=public
  if reserved:self.reserved_raw+=raw;self.reserved_public+=public
  else:self.normal_raw+=raw;self.normal_public+=public

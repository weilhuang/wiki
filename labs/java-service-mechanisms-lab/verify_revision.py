#!/usr/bin/env python3
"""Sequential baseline and source mutation checks, with no external dependencies.
SPDX-License-Identifier: MIT
"""
import pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
subprocess.run([sys.executable,'run.py','--output','proof/run-r4'],cwd=root,check=True,timeout=30)
subprocess.run([sys.executable,'regression_probes.py','--output','proof/r3-regressions'],cwd=root,check=True,timeout=55)
print('PASS: corrected baseline and all exact child/future mutation probes')

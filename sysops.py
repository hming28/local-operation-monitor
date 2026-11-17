# -*- coding: utf-8 -*-
"""Cross-platform OS abstraction router for local-ops."""

import sys

if sys.platform == "win32":
    from sysops_win32 import *  # noqa: F401, F403
else:
    from sysops_posix import *  # noqa: F401, F403

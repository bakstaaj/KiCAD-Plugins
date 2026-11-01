#!/usr/bin/env python3
"""Register the Move Selection Center to X/Y action."""

import os
import sys

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from move_selection_center import MoveSelectionCenterPlugin

MoveSelectionCenterPlugin().register()

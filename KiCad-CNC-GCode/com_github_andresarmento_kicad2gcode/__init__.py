#!/usr/bin/env python3
"""Register the Edge Cuts to G-code and Drill to G-code actions."""

import os
import sys

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from edgecuts2gcode import EdgeCuts2GcodePlugin
from drill2gcode import Drill2GcodePlugin

EdgeCuts2GcodePlugin().register()
Drill2GcodePlugin().register()

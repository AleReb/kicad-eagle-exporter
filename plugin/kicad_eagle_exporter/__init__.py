# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""KiCad 10 Action Plugin entry point. Export engines load on demand."""
from .action_plugin import EagleExportAction
EagleExportAction().register()

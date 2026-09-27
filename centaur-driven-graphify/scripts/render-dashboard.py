#!/usr/bin/env python3
"""Compatibility entry point. Generate Volante while preserving the old URL and notes."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('render-volante.py')), run_name='__main__')

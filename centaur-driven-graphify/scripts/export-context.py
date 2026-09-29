#!/usr/bin/env python3
"""Read current contract context as JSON without generating artifacts or indexing."""
import argparse
import json
from pathlib import Path
from volante import load_project

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    print(json.dumps(load_project(parser.parse_args().project), ensure_ascii=False))

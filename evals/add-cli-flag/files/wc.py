#!/usr/bin/env python3
"""Conta linhas de arquivos de texto: wc.py ARQUIVO..."""
import argparse
import sys


def count_lines(path):
    with open(path, encoding='utf-8') as source:
        return sum(1 for _ in source)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+')
    options = parser.parse_args(argv)
    for path in options.files:
        print(f'{count_lines(path)} {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

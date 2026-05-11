#!/usr/bin/env python3
"""Count 16-bit vs 32-bit Thumb / Thumb-2 instructions in an ARM ELF.

Disassembles the ELF with objdump and tabulates how many encodings are
16-bit Thumb vs 32-bit Thumb-2, both by instruction count and by bytes.

Honors ARM mapping symbols ($t/$d) which GCC and Clang emit by default:
literal pools and jump tables embedded in .text disassemble as
.word/.short/.byte directives and are excluded from the count.

The ELF must NOT have been stripped of mapping symbols (default `strip`
removes them).  Use the un-stripped output, or an intermediate .o.

Limitation: in mixed ARM/Thumb binaries (Cortex-A/R), a 32-bit ARM
instruction in an $a region looks the same width as a 32-bit Thumb-2
encoding and would be miscounted.  For Cortex-M (Thumb-only) this
doesn't arise.

Usage:
    python3 tools/count_thumb_widths.py <elf> [--objdump <path>]
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ADDR_RE = re.compile(r'^\s*[0-9a-fA-F]+:\s*$')
HEX_CHARS = set('0123456789abcdefABCDEF')


def classify_line(line):
    """Return 'thumb16', 'thumb32', 'data', or None for one objdump line."""
    parts = line.split('\t')
    if len(parts) < 3 or not ADDR_RE.match(parts[0]):
        return None
    hex_part, mnem_part = parts[1], parts[2].strip()
    if not mnem_part:
        return None
    if mnem_part.startswith('.'):
        return 'data'
    nybbles = sum(c in HEX_CHARS for c in hex_part)
    if nybbles == 4:
        return 'thumb16'
    if nybbles == 8:
        return 'thumb32'
    return None


def count_widths(elf_path, objdump):
    proc = subprocess.run(
        [objdump, '-d', str(elf_path)],
        check=True, capture_output=True, text=True,
    )
    counts = Counter()
    for line in proc.stdout.splitlines():
        kind = classify_line(line)
        if kind:
            counts[kind] += 1
    return counts


def main():
    ap = argparse.ArgumentParser(
        description='Count 16-bit vs 32-bit Thumb instructions in an ARM ELF.'
    )
    ap.add_argument('elf', type=Path, help='ELF file to analyze (un-stripped).')
    ap.add_argument('--objdump', default='arm-none-eabi-objdump',
                    help='objdump executable (default: arm-none-eabi-objdump)')
    args = ap.parse_args()

    counts = count_widths(args.elf, args.objdump)
    t16 = counts.get('thumb16', 0)
    t32 = counts.get('thumb32', 0)
    data = counts.get('data', 0)
    total = t16 + t32

    if total == 0:
        print(f'No Thumb instructions found in {args.elf}.', file=sys.stderr)
        print('Either the binary contains no code, or mapping symbols are '
              'missing (was the ELF stripped?).', file=sys.stderr)
        return 1

    bytes16 = 2 * t16
    bytes32 = 4 * t32
    bytes_total = bytes16 + bytes32

    print(f'{args.elf}:')
    print(f'  16-bit Thumb  : {t16:8d} instrs ({100*t16/total:5.1f}%)   '
          f'{bytes16:8d} bytes ({100*bytes16/bytes_total:5.1f}%)')
    print(f'  32-bit Thumb-2: {t32:8d} instrs ({100*t32/total:5.1f}%)   '
          f'{bytes32:8d} bytes ({100*bytes32/bytes_total:5.1f}%)')
    print(f'  Total code    : {total:8d} instrs           '
          f'{bytes_total:8d} bytes')
    print(f'  Data entries  : {data:8d} (literal pool / jump tables, excluded)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Watch a directory and print file changes line by line."""

import argparse
import ctypes
import os
import sys

# The C standard library, where the inotify functions live.
libc = ctypes.CDLL("libc.so.6", use_errno=True)

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage="%(prog)s [-h | --help] directory",
    )
    parser.add_argument("directory", help="directory to watch")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"Error: {args.directory} is not a directory.")

    # Ask the kernel for an inotify instance; it returns a file descriptor.
    fd = libc.inotify_init()
    if fd < 0:
        sys.exit(f"Error: inotify_init: {os.strerror(ctypes.get_errno())}")

    print(f"inotify file descriptor: {fd}")
    os.close(fd)


main()

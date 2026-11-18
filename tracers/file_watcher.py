#!/usr/bin/env python3
"""Watch a directory and print file changes line by line."""

import argparse
import ctypes
import os
import struct
import sys

# The C standard library, where the inotify functions live.
libc = ctypes.CDLL("libc.so.6", use_errno=True)

# Event types, with the values from the kernel header <sys/inotify.h>.
IN_MODIFY = 0x00000002  # file content was written
IN_ATTRIB = 0x00000004  # metadata changed (permissions, owner, ...)
IN_CREATE = 0x00000100  # file was created
IN_DELETE = 0x00000200  # file was deleted

# Every event starts with a fixed header: wd, mask, cookie, len.
EVENT_HEADER = struct.Struct("iIII")

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

    # Tell the kernel which directory to watch and which events we want.
    mask = IN_CREATE | IN_DELETE | IN_MODIFY | IN_ATTRIB
    wd = libc.inotify_add_watch(fd, os.fsencode(args.directory), mask)
    if wd < 0:
        sys.exit(f"Error: inotify_add_watch: {os.strerror(ctypes.get_errno())}")

    print(f"Watching {args.directory} (press Ctrl+C to stop)")
    try:
        while True:
            # Blocks until at least one event arrives.
            data = os.read(fd, 4096)
            offset = 0
            while offset < len(data):
                _, event_mask, _, name_len = EVENT_HEADER.unpack_from(data, offset)
                offset += EVENT_HEADER.size
                name = data[offset:offset + name_len].rstrip(b"\0").decode(errors="replace")
                offset += name_len

                if event_mask & IN_CREATE:
                    print(f"created   {name}")
                if event_mask & IN_DELETE:
                    print(f"deleted   {name}")
                if event_mask & IN_MODIFY:
                    print(f"modified  {name}")
                if event_mask & IN_ATTRIB:
                    print(f"attribute {name}")
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)

main()

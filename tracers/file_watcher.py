#!/usr/bin/env python3
"""Watch a directory and print file changes line by line."""

import argparse
import ctypes
import os
import stat
import sys

# The C standard library, where the inotify functions live.
#  With None we use the libc already loaded into Python (glibc, musl).
libc: ctypes.CDLL = ctypes.CDLL(None, use_errno=True)

# Event types, with the values from the kernel header <linux/inotify.h>.
IN_MODIFY = 0x00000002  # file content was written
IN_ATTRIB = 0x00000004  # metadata changed (permissions, owner, ...)
IN_MOVED_FROM = 0x00000040  # file was moved away (renamed or moved out)
IN_MOVED_TO = 0x00000080  # file was moved in (renamed or moved here)
IN_CREATE = 0x00000100  # file was created
IN_DELETE = 0x00000200  # file was deleted
IN_IGNORED = 0x00008000  # watch was removed (directory deleted)

# Options for inotify_add_watch, from the same header.
IN_ONLYDIR = 0x01000000  # fail if the path is not a directory
IN_DONT_FOLLOW = 0x02000000  # do not follow the path if it is a symbolic link

# The events we want from every watched directory.
EVENTS = IN_CREATE | IN_DELETE | IN_MODIFY | IN_ATTRIB | IN_MOVED_FROM | IN_MOVED_TO

# Header of every event, as defined by "struct inotify_event" in inotify(7).
# The file name follows it, padded with zero bytes to "len" bytes.
class InotifyEvent(ctypes.Structure):
    _fields_ = [
        ("wd", ctypes.c_int),
        ("mask", ctypes.c_uint32),
        ("cookie", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
    ]

# What we remember about each file: (size in bytes, mode).
FileInfo = tuple[int, int]

def read_info(path: str) -> FileInfo | None:
    """Return (size, mode) of a file, or None if it no longer exists."""
    try:
        st: os.stat_result = os.lstat(path)
    except FileNotFoundError:
        return None
    return st.st_size, st.st_mode

def format_mode(mode: int) -> str:
    """Format permissions as both octal and symbolic, e.g. '644 (rw-r--r--)'."""
    return f"{stat.S_IMODE(mode):03o} ({stat.filemode(mode)[1:]})"

def scan_directory(fd: int, watches: dict[int, str], files: dict[str, FileInfo],
                   root: str, directory: str) -> None:
    """Remember the files in a watched directory and watch its subdirectories."""
    try:
        entries: list[os.DirEntry[str]] = list(os.scandir(os.path.join(root, directory)))
    except OSError:
        return  # already gone, or not readable
    for entry in entries:
        path: str = os.path.join(directory, entry.name)
        info: FileInfo | None = read_info(entry.path)
        if info is None:
            continue
        files[path] = info
        if stat.S_ISDIR(info[1]):
            watch_directory(fd, watches, files, root, path)

def watch_directory(fd: int, watches: dict[int, str], files: dict[str, FileInfo],
                    root: str, directory: str) -> None:
    """Watch a subdirectory, then everything inside it."""
    # Only a real directory: the path may have been replaced by a symbolic
    # link or a file since we looked at it.
    wd: int = libc.inotify_add_watch(fd, os.fsencode(os.path.join(root, directory)),
                                     EVENTS | IN_ONLYDIR | IN_DONT_FOLLOW)
    if wd < 0:
        print(f"Warning: cannot watch {os.path.join(root, directory)}: "
              f"{os.strerror(ctypes.get_errno())}", file=sys.stderr)
        return
    watches[wd] = directory
    scan_directory(fd, watches, files, root, directory)

def handle_event(files: dict[str, FileInfo], directory: str, event_mask: int, name: str) -> None:
    """Compare the file with what we remember and print what changed."""
    old: FileInfo | None = files.get(name)

    if event_mask & IN_DELETE:
        files.pop(name, None)
        print(f"deleted      {name}")
        return

    if event_mask & IN_MOVED_FROM:
        files.pop(name, None)
        print(f"moved away   {name}")
        return

    # A new name in the directory: report it before looking at the file.
    # Therefore it is printed even if the file disappears right away.
    if event_mask & IN_CREATE:
        print(f"created      {name}")
    elif event_mask & IN_MOVED_TO:
        print(f"moved in     {name}")

    new: FileInfo | None = read_info(os.path.join(directory, name))
    if new is None:
        return  # already gone; the delete or move event will follow
    files[name] = new

    # Nothing to compare with for a new name, or a file we did not know.
    if event_mask & (IN_CREATE | IN_MOVED_TO) or old is None:
        return

    old_size, old_mode = old
    new_size, new_mode = new
    if new_size != old_size:
        print(f"size         {name}: {old_size} -> {new_size} bytes")
    if stat.S_IMODE(new_mode) != stat.S_IMODE(old_mode):
        print(f"permissions  {name}: {format_mode(old_mode)} -> {format_mode(new_mode)}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage="%(prog)s [-h | --help] directory",
    )
    parser.add_argument("directory", help="directory to watch")
    args: argparse.Namespace = parser.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"Error: {args.directory} is not a directory.")

    # Ask the kernel for an inotify instance; it returns a file descriptor.
    fd: int = libc.inotify_init()
    if fd < 0:
        sys.exit(f"Error: inotify_init: {os.strerror(ctypes.get_errno())}")

    # Tell the kernel which directory to watch and which events we want.
    wd: int = libc.inotify_add_watch(fd, os.fsencode(args.directory), EVENTS)
    if wd < 0:
        sys.exit(f"Error: inotify_add_watch: {os.strerror(ctypes.get_errno())}")

    # Remember the size and permissions of the files that already exist.
    files: dict[str, FileInfo] = {}
    for entry in os.scandir(args.directory):
        info: FileInfo | None = read_info(entry.path)
        if info is not None:
            files[entry.name] = info

    print(f"Watching {args.directory} (press Ctrl+C to stop)")
    try:
        while True:
            # Blocks until at least one event arrives.
            data: bytes = os.read(fd, 4096)
            offset: int = 0
            while offset < len(data):
                event: InotifyEvent = InotifyEvent.from_buffer_copy(data, offset)
                offset += ctypes.sizeof(InotifyEvent)
                name: str = data[offset:offset + event.len].rstrip(b"\0").decode(errors="replace")
                offset += event.len
                # An event about the watched directory itself, with no name, not about a file inside it.
                if not name:
                    continue
                handle_event(files, args.directory, event.mask, name)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)

main()

# Tracers

Tools that watch what happens inside a VM.

## file_watcher.py

Watches a directory and prints, line by line, every file that is created,
deleted, moved, resized or whose permissions change. It uses the Linux
kernel's inotify interface directly, so it needs nothing beyond Python.

### Requirements

- Linux
- Python 3.10 or newer

### Usage

Run it with Python, from `~/vm_tracers/tracers`:

```console
$ python3 file_watcher.py DIRECTORY
```

Or run it directly. The script is already executable in the repository;
if it is not on your machine, make it executable first. From `~/vm_tracers/tracers`:

```console
$ chmod +x file_watcher.py
$ ./file_watcher.py DIRECTORY
```

Press Ctrl+C to stop.

### Example

Terminal 1, from `~/vm_tracers/tracers`, start watching an empty test directory:

```console
$ mkdir -p /tmp/test_watch
$ ./file_watcher.py /tmp/test_watch
Watching /tmp/test_watch (press Ctrl+C to stop)
```

Terminal 2, from `/tmp/test_watch`, change some files in it:

```console
$ echo hi > a.txt
$ chmod 755 a.txt
$ echo more >> a.txt
$ mv a.txt b.txt
$ rm b.txt
```

Terminal 1 now shows:

```console
created      a.txt
permissions  a.txt: 644 (rw-r--r--) -> 755 (rwxr-xr-x)
size         a.txt: 3 -> 8 bytes
moved away   a.txt
moved in     b.txt
deleted      b.txt
```

`moved away` and `moved in` are reported for renames as well as for files
moved out of or into the directory.

When you are done, stop the watcher with Ctrl+C and remove the test
directory. Files in `/tmp` are not deleted right away; on most systems
they are only cleaned up at reboot.

```console
$ rm -rf /tmp/test_watch
```

### Limitations

- Only files directly inside the directory are watched, not subdirectories.
- The size and permissions are read when an event is handled, not when the
  change happened, so changes made in quick succession can be merged into
  one line. For example, from `/tmp/test_watch`:

  ```console
  $ touch a.txt
  $ echo hi >> a.txt; echo hi >> a.txt
  ```

  Each `echo` adds 3 bytes, but the watcher may print a single line:

  ```console
  size         a.txt: 0 -> 6 bytes
  ```
- The kernel keeps a limited number of events waiting to be read (16384 by
  default). Events beyond that are dropped without being reported. To see
  the limit on your machine:

  ```console
  $ cat /proc/sys/fs/inotify/max_queued_events
  16384
  ```

  To reproduce it, run these commands in one terminal, from
  `~/vm_tracers/tracers`. They start the watcher in the background, pause
  it, create 20000 files while it is paused, then let it continue and stop
  it cleanly:

  ```console
  $ rm -rf /tmp/test_watch
  $ mkdir /tmp/test_watch
  $ ./file_watcher.py /tmp/test_watch > /tmp/watch.log &
  $ watcher=$!
  $ kill -STOP $watcher
  $ python3 -c "for i in range(20000): open(f'/tmp/test_watch/f{i}', 'w').close()"
  $ kill -CONT $watcher
  $ sleep 5
  $ kill -INT $watcher
  ```

  The shell prints job status lines such as `[1]+  Stopped`; they are
  expected. Then count the reported files. Only as many as the limit
  allows are listed:

  ```console
  $ grep -c created /tmp/watch.log
  16384
  ```

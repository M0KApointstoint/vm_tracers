# Syscall tracing for Docker containers

Traces the system calls of any running Docker container with `strace` and
saves the full output plus a per-syscall summary to `reports/`.

```
syscall_tracer/
  README.md
  reports/               generated reports (one .log per run, created automatically)
  tracers/
    syscall_tracer.py    the tracer
```

## How it works

`strace` is not run on the host. The script starts a small helper container
(the *sidecar*) that has `strace` and shares the target's PID namespace
(`--pid=container:<target>`). From there it attaches to the container's main
process (PID 1) and follows every process it creates (`-f`).

Because everything goes through the Docker daemon, the same script works on
your own machine and on Docker inside a VM, with no code changes. The target
container does not need `strace` and is not modified.

## 1. Setup

Only Docker and Python 3 are needed. `strace` does **not** need to be
installed on the host; it lives in the sidecar image.

### Arch
```bash
sudo pacman -S docker python
sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # log out/in to use docker without sudo
docker run --rm hello-world        # sanity check
```

### Ubuntu / Debian (e.g. inside a Lima VM)
```bash
sudo apt-get update
sudo apt-get install -y docker.io python3
sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # log out/in (or exit and re-enter the shell)
```

> Lima mounts your home directory **read-only** by default. Clone the repo
> inside the VM (or set `writable: true` on the mount), otherwise the script
> cannot write `reports/`.

## 2. Usage
```bash
python3 tracers/syscall_tracer.py <container>     # name or ID (short ID works)
```
Press **Ctrl+C** to stop. `strace` detaches cleanly and the target container
keeps running. If the traced program exits on its own, tracing stops too.

On the first run the script builds the `strace-sidecar` image
(`alpine:3.20` + `strace`), so it needs internet once. Later runs reuse it.

### Quick test
Any running container works. A minimal one that generates predictable
syscalls:
```bash
docker run -d --name test ubuntu:24.04 sh -c \
  'while true; do cat /etc/hostname >/dev/null; ls /nonexistent 2>/dev/null; sleep 1; done'

python3 tracers/syscall_tracer.py test            # ~10 s, then Ctrl+C
grep '/nonexistent' reports/test_*.log | head -2  # should show = -1 ENOENT
docker rm -f test
```

## 3. Output
Each run creates a new file:
```
reports/<container-name>_<YYYY-MM-DD_HH-MM-SS>.log
```
It contains:
- a header with container name, ID and start time
- the raw `strace -f -tt` output (one line per syscall, with PID and timestamp)
- the stop time and a summary table: calls, errors (`= -1 E...`) and % per syscall

The summary is also printed in the terminal.

## 4. Tracing Docker in a VM from the host (optional)
The script only talks to the Docker daemon, so it can run on the host and
trace containers inside the VM. The sidecar is started on the VM's daemon:
```bash
export DOCKER_HOST=ssh://user@vm-address    # or: docker context use <vm-context>
python3 tracers/syscall_tracer.py <container>
```
The report is still written on the machine that runs the script.

## 5. Cleanup
```bash
docker rmi strace-sidecar        # optional, removes the helper image
```

## Notes
- No root is needed beyond access to Docker (being in the `docker` group).
  The sidecar gets `CAP_SYS_PTRACE` and `seccomp=unconfined` so `strace` can
  use ptrace on the target's processes.
- `strace` stops the process on every syscall, which slows it down noticeably.
  Fine for behaviour analysis, wrong for performance numbers. An eBPF tracer
  (bpftrace / bcc) is the low-overhead alternative.
- Only PID 1 and the processes it creates **after** attaching are traced.
  Children that already existed are missed, and so is a `docker exec` started
  later. For the same reason, containers started with `docker run --init`
  are not traced correctly: PID 1 becomes `tini` and the real program is an
  already-running child.
- The target container must be running; the script exits with a message if it
  does not exist or is stopped.
- Ctrl+C does not stop a program that runs as PID 1 in a container unless it
  installs its own SIGINT handler (the kernel ignores default-action signals
  for PID 1). Use `docker stop` / `docker kill` instead.

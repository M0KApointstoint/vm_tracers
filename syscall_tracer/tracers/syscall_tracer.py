#!/usr/bin/env python3

import re
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SIDECAR_IMAGE = "strace-sidecar:latest"
SIDECAR_DOCKERFILE = "FROM alpine:3.20\nRUN apk add --no-cache strace\n"

# [pid  123] 10:00:00.123456 openat(AT_FDCWD, "/etc/x", O_RDONLY) = -1 ENOENT (...)
CALL_RE = re.compile(r"^(?:\[pid\s+\d+\]\s+)?\d{2}:\d{2}:\d{2}\.\d+\s+(\w+)\(")
# [pid  123] 10:00:00.123456 <... read resumed>"abc", 3) = 3
RESUMED_RE = re.compile(r"<\.\.\. (\w+) resumed>")
ERROR_RE = re.compile(r"=\s+-1\s+E[A-Z0-9]+")


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kwargs)


def get_container_name(container):
    """Verifica ca containerul exista si ruleaza; intoarce numele lui."""
    r = docker("inspect", "-f", "{{.Name}} {{.State.Running}}", container)
    if r.returncode != 0:
        sys.exit(f"[!] Containerul '{container}' nu exista.")
    name, running = r.stdout.split()
    if running != "true":
        sys.exit(f"[!] Containerul '{container}' nu ruleaza.")
    return name.lstrip("/")


def ensure_sidecar_image():
    """Construieste o singura data imaginea cu strace."""
    if docker("image", "inspect", SIDECAR_IMAGE).returncode == 0:
        return
    print(f"[*] Construiesc imaginea {SIDECAR_IMAGE} (doar prima data)...")
    r = docker("build", "-t", SIDECAR_IMAGE, "-", input=SIDECAR_DOCKERFILE)
    if r.returncode != 0:
        sys.exit(f"[!] Build esuat:\n{r.stderr}")


def summary(calls, errors):
    total = sum(calls.values())
    lines = [f"\n=== Sumar: {total} syscall-uri ===",
             f"{'syscall':<20}{'apeluri':>10}{'erori':>8}{'%':>8}"]
    for name, n in calls.most_common():
        lines.append(f"{name:<20}{n:>10}{errors[name]:>8}{100 * n / total:>7.1f}%")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        sys.exit("Folosire: python3 syscall_tracer.py <container_id>")
    container = sys.argv[1]

    name = get_container_name(container)
    ensure_sidecar_image()

    REPORTS_DIR.mkdir(exist_ok=True)
    report = REPORTS_DIR / f"{name}_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

    sidecar = f"strace-sidecar-{uuid.uuid4().hex[:8]}"
    cmd = ["docker", "run", "--rm", "-i", "--name", sidecar,
           f"--pid=container:{container}",       # vedem procesele containerului tinta
           "--cap-add", "SYS_PTRACE",             # strace are nevoie de ptrace
           "--security-opt", "seccomp=unconfined",
           SIDECAR_IMAGE, "strace", "-f", "-tt", "-p", "1"]

    print(f"[*] Tracing pe '{name}'. Ctrl+C pentru stop.")
    print(f"[*] Raport: {report}")

    calls, errors = Counter(), Counter()
    # strace scrie pe stderr -> il citim linie cu linie
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, errors="replace")

    with open(report, "w") as out:
        out.write(f"# Container: {name} ({container})\n# Start: {datetime.now()}\n\n")
        try:
            for line in proc.stderr:
                print(line, end="")
                out.write(line)

                m = CALL_RE.match(line)
                if m and "resumed>" not in line:
                    syscall = m.group(1)
                    calls[syscall] += 1
                else:
                    r = RESUMED_RE.search(line)
                    syscall = r.group(1) if r else None
                if syscall and ERROR_RE.search(line):
                    errors[syscall] += 1
        except KeyboardInterrupt:
            docker("kill", "-s", "INT", sidecar)  # strace se detaseaza curat
        finally:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                docker("rm", "-f", sidecar)

        text = summary(calls, errors)
        out.write(f"\n# Stop: {datetime.now()}\n{text}\n")

    print(text)
    print(f"\n[*] Salvat in: {report}")


if __name__ == "__main__":
    main()

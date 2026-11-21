syscall_tracer.py - syscall tracing pentru un container Docker.

Folosire:
    python3 syscall_tracer.py <container_id>

Ctrl+C opreste tracing-ul. Tot output-ul (trace + sumar) se salveaza in
"syscall reports/<container>_<data>_<ora>.log", langa script.

Cum merge: pornim un container "sidecar" cu strace care intra in
namespace-ul de PID-uri al containerului tinta (--pid=container:<id>)
si ruleaza `strace -f -p 1` (procesul principal + toti copiii lui).
Merge la fel local sau pe un daemon Docker dintr-un VM
(DOCKER_HOST=ssh://user@vm sau `docker context use <vm>`).
"""

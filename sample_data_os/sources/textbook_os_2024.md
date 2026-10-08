# Modern Operating Systems in Practice, 3rd Edition (2024) – Selected Excerpts

## Chapter 3: Processes and Threads
Threads of the same process share one address space, so a bug in one thread can corrupt data used by the others.
Context switching between threads of the same process is cheaper than switching between processes because the memory mapping does not change.

## Chapter 5: Scheduling in Linux
Linux replaced the O(1) scheduler with the Completely Fair Scheduler (CFS) in kernel 2.6.23, released in 2007.
Since Linux 6.6, released in 2023, the EEVDF scheduler has replaced CFS as the default scheduler for normal tasks.

---page---

## Chapter 6: Deadlocks
Coffman showed that deadlock requires four conditions together: mutual exclusion, hold and wait, no preemption and circular wait.
Breaking any one of the four conditions, for example by ordering locks to prevent circular wait, prevents deadlock.

## Chapter 8: Page Replacement
FIFO page replacement can suffer from Belady's anomaly, where giving a process more frames increases its page faults.
Stack algorithms such as LRU and the optimal algorithm never suffer from Belady's anomaly.

---page---

## Chapter 11: System Startup
Most major Linux distributions now use systemd as the init system that runs as PID 1 and starts services in parallel.

## Chapter 13: Containers
Linux containers isolate processes using namespaces and limit their CPU and memory using control groups (cgroups).
A container shares the host kernel, so it starts much faster than a virtual machine that boots its own kernel.

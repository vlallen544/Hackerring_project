# Expected Results – Operating Systems course (answer key for testing agents)

## Conflicts the Reconciler should find
1. Linux scheduler: Notes 2017 ("O(1) scheduler") vs Textbook 2024 (CFS since 2.6.23, EEVDF since 6.6) + Backend JD
   -> outdated; Textbook wins (newer, more specific)
2. Linux init / PID 1: Notes 2017 ("SysV init") vs Textbook 2024 + SRE JD ("systemd runs as PID 1")
   -> outdated; Textbook + JD win (newer, more sources agree)
3. Deadlock conditions: Blog 2014 ("only two conditions") vs Notes 2017 + Textbook 2024 (four Coffman conditions)
   -> Notes + Textbook win (authority, two sources agree)
4. "More frames always reduce page faults": Blog 2014 -> unreliable (Belady's anomaly in Notes and Textbook)
5. "Threads have separate address spaces": Blog 2014 -> wrong (Notes and Textbook: threads share one address space)
6. "Round Robin is always the best": Blog 2014 -> flagged unreliable (absolute claim)

## Syllabus gaps (in JDs, missing from faculty notes)
Missing: containers (namespaces, cgroups)
Outdated: Linux CPU scheduler, Linux init / systemd
Covered: processes and threads, synchronization and deadlocks, virtual memory and paging

## Prerequisite chain (expected, roughly)
Processes -> Threads -> Synchronization -> Deadlocks
Processes -> CPU Scheduling
Memory management (paging) -> Virtual memory (page replacement)
Processes -> Linux boot / init ; Processes + Memory -> Containers

# Operating Systems – Lecture Notes, Units 1 to 5 (Prepared by Prof. S. Rao, 2017)

## 1. Processes
A process is a program in execution, with its own address space, program counter, registers and open files.
A process moves between the states new, ready, running, waiting and terminated.
The operating system keeps information about each process in a process control block (PCB).

## 2. Threads
A thread is the smallest unit of CPU scheduling inside a process.
Threads of the same process share the code, data and heap of that process, but each thread has its own stack and registers.
Creating a thread is cheaper than creating a process because no new address space is needed.

---page---

## 3. CPU Scheduling
First-Come First-Served (FCFS) scheduling can make short jobs wait behind long ones, which is called the convoy effect.
Shortest Job First (SJF) gives the minimum average waiting time but needs to know burst times in advance.
Round Robin gives each process a fixed time quantum and is used in time-sharing systems.
The Linux kernel uses the O(1) scheduler, which picks the next task in constant time using priority arrays.

## 4. Process Synchronization
A race condition happens when the result depends on the order in which threads access shared data.
A critical section must satisfy mutual exclusion, progress and bounded waiting.
A semaphore is an integer variable accessed only through the atomic operations wait and signal.

---page---

## 5. Deadlocks
A deadlock can occur only if four conditions hold at the same time: mutual exclusion, hold and wait, no preemption and circular wait.
The Banker's algorithm avoids deadlock by granting a request only if the system stays in a safe state.

## 6. Memory Management
Paging divides physical memory into fixed-size frames and logical memory into pages of the same size.
Paging removes external fragmentation but can still cause internal fragmentation in the last page.
A Translation Lookaside Buffer (TLB) caches recent page-table entries to speed up address translation.

---page---

## 7. Virtual Memory
Demand paging loads a page into memory only when it is first accessed, causing a page fault.
With FIFO page replacement, adding more frames can sometimes increase the number of page faults; this is called Belady's anomaly.
The LRU algorithm replaces the page that has not been used for the longest time.

## 8. Booting Linux
After the kernel starts, Linux runs SysV init as the first process with PID 1, which starts services using runlevel scripts.

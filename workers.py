"""Multithreaded job system."""

import sys
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = ""
    class Style:
        RESET_ALL = ""


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Job:
    id: int = 0
    filename: str = ""
    input_path: str = ""
    output_path: str = ""
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    pages_done: int = 0
    pages_total: int = 0
    message: str = ""
    error: str = ""
    worker_id: int = -1
    start_time: float = 0.0
    end_time: float = 0.0
    metadata_info: str = ""
    dry_run_output: str = ""

    @property
    def elapsed(self):
        if self.start_time == 0:
            return 0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time


class WorkerPool:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.jobs: list[Job] = []
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self.on_job_update: Optional[Callable] = None
        self.on_log: Optional[Callable] = None
        self._active: dict[int, str] = {}

    def cancel(self):
        self._cancel.set()

    @property
    def cancelled(self):
        return self._cancel.is_set()

    def _log(self, msg, color=""):
        if self.on_log:
            self.on_log(msg, color)
        elif HAS_COLOR and color:
            print(f"{color}{msg}{Style.RESET_ALL}")
        else:
            print(msg)

    def _update(self, job):
        if self.on_job_update:
            self.on_job_update(job)

    def run_jobs(self, jobs, task_fn, sequential=False):
        self.jobs = jobs
        self._cancel.clear()
        self._active.clear()

        workers = 1 if sequential else min(self.max_workers, len(jobs))
        self._log(f"Starting {len(jobs)} jobs with {workers} worker(s)",
                  Fore.CYAN if HAS_COLOR else "")

        start = time.time()

        def run_one(job, wid):
            if self._cancel.is_set():
                job.status = JobStatus.SKIPPED
                self._update(job)
                return

            job.status = JobStatus.RUNNING
            job.worker_id = wid
            job.start_time = time.time()
            with self._lock:
                self._active[wid] = job.filename
            self._update(job)

            def progress_cb(c, t):
                job.pages_done = c
                job.pages_total = t
                job.progress = c / t if t else 0
                self._update(job)

            def log_cb(msg):
                job.message = msg
                self._log(f"  [W{wid}] {msg}")

            try:
                task_fn(job, progress_cb, log_cb, self._cancel)
                job.status = JobStatus.DONE
                job.end_time = time.time()
                job.progress = 1.0
                self._log(f"  ✓ {job.filename} ({job.elapsed:.1f}s)",
                          Fore.GREEN if HAS_COLOR else "")
            except Exception as e:
                job.status = JobStatus.FAILED
                job.end_time = time.time()
                job.error = str(e)
                self._log(f"  ✗ {job.filename}: {e}",
                          Fore.RED if HAS_COLOR else "")

            with self._lock:
                self._active.pop(wid, None)
            self._update(job)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_one, j, i % workers): j for i, j in enumerate(jobs)}
            for fut in as_completed(futures):
                pass

        elapsed = time.time() - start
        done = sum(1 for j in jobs if j.status == JobStatus.DONE)
        failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
        self._log(f"\nComplete: {done} ok, {failed} failed ({elapsed:.1f}s)",
                  Fore.CYAN if HAS_COLOR else "")
        return jobs


class TerminalProgress:
    def __init__(self, pool):
        self.pool = pool
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)

    def _loop(self):
        while self._running:
            self._render()
            time.sleep(0.3)
        self._render()

    def _render(self):
        jobs = self.pool.jobs
        if not jobs:
            return
        lines = []
        total = len(jobs)
        done = sum(1 for j in jobs if j.status == JobStatus.DONE)
        failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
        pct = (done + failed) / total if total else 0
        bar = self._bar(pct, 30)
        lines.append(f"{Fore.CYAN}Overall:{Style.RESET_ALL} {bar} "
                     f"{Fore.GREEN}{done}{Style.RESET_ALL}/"
                     f"{Fore.RED}{failed}{Style.RESET_ALL}/{total}"
                     if HAS_COLOR else f"Overall: {bar} {done}/{failed}/{total}")
        for j in jobs:
            if j.status == JobStatus.RUNNING:
                pbar = self._bar(j.progress, 20)
                pg = f"{j.pages_done}/{j.pages_total}" if j.pages_total else "..."
                name = j.filename[:35].ljust(35)
                lines.append(f"  {Fore.YELLOW}W{j.worker_id}{Style.RESET_ALL} {name} {pbar} {pg}"
                             if HAS_COLOR else f"  W{j.worker_id} {name} {pbar} {pg}")
        n = len(lines)
        if n:
            sys.stdout.write(f"\033[{n}A\033[J")
        for line in lines:
            sys.stdout.write(line + "\n")
        sys.stdout.flush()

    @staticmethod
    def _bar(pct, w=20):
        f = int(pct * w)
        if HAS_COLOR:
            return f"{Fore.GREEN}{'█'*f}{Fore.WHITE}{'░'*(w-f)}{Style.RESET_ALL} {int(pct*100):3d}%"
        return f"[{'█'*f}{'░'*(w-f)}] {int(pct*100):3d}%"
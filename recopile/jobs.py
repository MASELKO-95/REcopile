from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from .network import Cancelled


class Jobs:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recopile-task")
        self.events = {}
        self.lock = threading.RLock()

    def submit(self, kind, title, target, work):
        with self.lock:
            for existing in self.store.list("jobs"):
                if existing["status"] in ("queued", "running") and existing.get("target") == target and existing["kind"] == kind:
                    return existing
            ident = uuid.uuid4().hex
            event = threading.Event()
            self.events[ident] = event
            job = {"id": ident, "kind": kind, "title": title, "target": target, "status": "queued", "progress": 0,
                   "downloaded": 0, "total": 0, "message": "Oczekuje w kolejce", "created_at": time.time()}
            self.store.put("jobs", ident, job)
            self.pool.submit(self._run, ident, work)
            return job

    def _run(self, ident, work):
        def update(**values):
            with self.lock:
                current = self.store.get("jobs", ident)
                self.store.put("jobs", ident, {**current, **values})
        event = self.events[ident]
        try:
            if event.is_set():
                raise Cancelled("Anulowano zadanie.")
            update(status="running", message="Rozpoczynanie", started_at=time.time())
            result = work(update, event.is_set)
            update(status="completed", progress=100, message="Gotowe", result=result, finished_at=time.time())
        except Cancelled as exc:
            update(status="cancelled", message=str(exc), finished_at=time.time())
        except Exception as exc:
            log = self.store.root / "logs"
            log.mkdir(exist_ok=True)
            (log / f"{ident}.log").write_text(traceback.format_exc())
            update(status="failed", message=str(exc) or "Zadanie nie powiodło się.", finished_at=time.time(), log=str(log / f"{ident}.log"))
        finally:
            with self.lock:
                self.events.pop(ident, None)

    def cancel(self, ident):
        with self.lock:
            event = self.events.get(ident)
            if event:
                event.set()
                return {"ok": True}
        return {"ok": False, "message": "Zadanie już się zakończyło."}

    def list(self):
        return sorted(self.store.list("jobs"), key=lambda j: j["created_at"], reverse=True)[:100]

    def shutdown(self):
        with self.lock:
            for event in self.events.values():
                event.set()
        self.pool.shutdown(wait=False, cancel_futures=True)

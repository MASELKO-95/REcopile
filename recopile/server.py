from __future__ import annotations

import json
import mimetypes
import re
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .network import UserError


def create_server(launcher, port=4783):
    token = secrets.token_urlsafe(32)
    static = (launcher.app_root / "frontend/dist/client").resolve()
    if not (static / "index.html").is_file():
        raise UserError("Brak zbudowanego interfejsu. Uruchom ./start.sh albo npm run build w folderze frontend.")

    class Handler(BaseHTTPRequestHandler):
        server_version = "Recopile"

        def log_message(self, fmt, *args):
            if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
                super().log_message(fmt, *args)

        def valid_origin(self):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts:
                return False
            origin = self.headers.get("Origin")
            return not origin or origin in {"http://" + host for host in hosts}

        def common_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

        def send_json(self, payload, status=200):
            raw = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.common_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.valid_origin():
                self.send_json({"error": "Niedozwolony adres lub pochodzenie żądania."}, 403)
                return
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if path == "/api/bootstrap":
                    self.send_json({**launcher.bootstrap(), "token": token})
                elif path == "/api/games":
                    mode = "recompile" if launcher.preferences()["only_recompiled"] else query.get("mode", "all")
                    self.send_json(launcher.query(q=query.get("q", ""), platform=query.get("platform", "all"), mode=mode,
                        view=query.get("view", "catalog"), device_only=query.get("device") == "1", sort=query.get("sort", "featured"), limit=int(query.get("limit", 24)), offset=int(query.get("offset", 0))))
                elif path.startswith("/api/games/"):
                    self.send_json(launcher.detail(path.removeprefix("/api/games/")))
                elif path == "/api/status":
                    self.send_json({"jobs": launcher.jobs.list(), "media_revision": launcher.media.revision, "running": launcher.active_processes(), "stats": launcher.store.stats(),
                        "sources": launcher.store.list("sources"), "engines": launcher.engines(), "last_update_check": launcher.store.get("settings", "last_update_check"),
                        "launcher_update": launcher.store.get("settings", "launcher_update"), "libraries": launcher.libraries(),
                        'catalog_sync':launcher.store.get('settings','catalog_sync'),
                        "pending_updates":launcher.store.get("settings", "pending_updates", []), "profile":launcher.profiles.summary()})
                elif path == "/api/profile":
                    self.send_json(launcher.profiles.summary())
                elif path == "/api/collections":
                    self.send_json(launcher.collections())
                elif path == "/api/steam":
                    self.send_json(launcher.steam.state())
                elif path == "/api/workshop":
                    self.send_json(launcher.workshop.state())
                elif path == '/api/performance':
                    self.send_json(launcher.performance.state())
                elif path == "/api/reports":
                    self.send_json({"local":launcher.store.list("compatibility_reports"), "public":launcher.compatibility.public_reports(), "device":launcher.compatibility.device})
                elif path.startswith("/api/covers/"):
                    filename = path.removeprefix("/api/covers/")
                    if not re.fullmatch(r"[a-f0-9]{64}\.(?:png|jpg|webp)", filename):
                        self.send_json({"error": "Niepoprawny adres okładki."}, 400)
                        return
                    cover_root = (launcher.store.root / "covers").resolve()
                    candidate = (cover_root / filename).resolve()
                    if not candidate.is_relative_to(cover_root) or not candidate.is_file():
                        self.send_json({"error": "Okładka nie została pobrana."}, 404)
                        return
                    raw = candidate.read_bytes()
                    self.send_response(200)
                    self.common_headers()
                    self.send_header("Content-Type", mimetypes.guess_type(filename)[0])
                    self.send_header("Cache-Control", "private, max-age=31536000, immutable")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                elif path.startswith("/api/"):
                    self.send_json({"error": "Nieznane żądanie."}, 404)
                else:
                    candidate = (static / path.lstrip("/")).resolve()
                    if not candidate.is_relative_to(static):
                        self.send_json({"error": "Niedozwolona ścieżka."}, 403)
                        return
                    if not candidate.is_file():
                        if path == "/" or "." not in Path(path).name:
                            candidate = static / "index.html"
                        else:
                            self.send_json({"error": "Nie znaleziono pliku."}, 404)
                            return
                    raw = candidate.read_bytes()
                    self.send_response(200)
                    self.common_headers()
                    self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
                    self.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=3600")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
            except (UserError, ValueError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception:
                self.send_json({"error": "Wewnętrzny błąd launchera. Szczegóły są w terminalu."}, 500)
                import traceback
                traceback.print_exc()

        def do_POST(self):
            if not self.valid_origin() or self.headers.get("X-Recopile-Token") != token:
                self.send_json({"error": "Żądanie nie pochodzi z tej sesji launchera."}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 256000 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise UserError("Niepoprawny format żądania.")
                data = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(data, dict):
                    raise UserError("Niepoprawny format danych.")
                path = urlparse(self.path).path
                ident = data.get("game_id", "")
                if path == "/api/settings":
                    result = launcher.save_preferences(data)
                elif path == "/api/notice":
                    result = launcher.finish_notice(data)
                elif path == "/api/project-info":
                    result = launcher.project_information(data.get("source_id"))
                elif path == "/api/review-seen":
                    result = launcher.documents.seen(data.get("fingerprint"))
                elif path == "/api/accept-review":
                    documents = launcher.project_information(data.get("source_id"))
                    result = launcher.documents.accept(documents, data.get("fingerprint"), auto=bool(data.get("allow_auto")),
                        license_accepted=data.get('license_accepted'), license_hash=data.get('license_hash'))
                    launcher.documents.seen(documents["fingerprint"])
                elif path == "/api/profile/create":
                    result = launcher.profiles.create(data.get("name", ""))
                elif path == "/api/profile/switch":
                    result = launcher.profiles.switch(data.get("profile_id"))
                elif path == "/api/profile/export":
                    result = launcher.profiles.export_png()
                elif path == "/api/compatibility":
                    result = launcher.compatibility.submit_local(launcher.require_game(ident), data, launcher.preferences())
                elif path == "/api/sync-catalog":
                    result = launcher.sync_catalog()
                elif path == "/api/sources":
                    result = launcher.add_source(data)
                elif path == '/api/performance/hardware':
                    result = launcher.performance.collect_hardware()
                elif path == '/api/performance/start':
                    result = launcher.performance.start(data)
                elif path == '/api/performance/stop':
                    result = launcher.performance.finish(data.get('session_id'))
                elif path == '/api/performance/import':
                    result = launcher.performance.import_log(data)
                elif path == '/api/performance/export':
                    result = launcher.performance.public_report(data.get('session_id'))
                elif path == "/api/source/edit":
                    result = launcher.update_source(data.get("source_id"),data)
                elif path == "/api/inspect-source":
                    result = launcher.inspect_source(data.get("repo", ""))
                elif path == "/api/local-game":
                    result = launcher.add_local_game(data)
                elif path == "/api/steam/scan":
                    result = launcher.steam.scan()
                elif path == "/api/steam/settings":
                    result = launcher.steam.configure(data)
                elif path == "/api/steam/library":
                    result = launcher.steam.library(data)
                elif path == "/api/project/local":
                    result = launcher.bind_project(data)
                elif path == "/api/mod/inspect":
                    result = launcher.workshop.inspect(data.get('path',''))
                elif path == "/api/mod/template":
                    result=launcher.workshop.template(data.get('game_id',''))
                elif path == "/api/mod/install":
                    with launcher.process_lock:
                        review=launcher.workshop.inspect(data.get('path',''))
                        if review['manifest']['game_id'] in launcher.running: raise UserError('Zamknij grę przed instalacją moda.')
                        result = launcher.workshop.install(data.get('path',''),data.get('fingerprint',''),data.get('trusted') is True,data.get('overwrite') is True,
                            license_accepted=data.get('license_accepted'),license_hash=data.get('license_hash'))
                elif path == "/api/mod/remove":
                    with launcher.process_lock:
                        mod=launcher.store.get('mods',data.get('mod_id',''),{})
                        if mod.get('game_id') in launcher.running: raise UserError('Zamknij grę przed usunięciem moda.')
                        result=launcher.workshop.remove(data.get('mod_id',''))
                elif path == "/api/library":
                    result = launcher.add_library(ident, data.get("added", True))
                elif path == "/api/media":
                    result = launcher.request_media(data)
                elif path == "/api/install":
                    result = launcher.install(data.get("source_id"), ident, review=data.get("review_fingerprint"), allow_auto=bool(data.get("allow_auto")),
                        license_accepted=data.get('license_accepted'), license_hash=data.get('license_hash'))
                elif path == "/api/import":
                    result = launcher.import_game(ident, data)
                elif path == "/api/port-setup":
                    result = launcher.port_setup.prepare(ident, data)
                elif path == "/api/executable":
                    result = launcher.register_executable(ident, data)
                elif path == "/api/ready":
                    result = launcher.mark_ready(ident)
                elif path == "/api/launch":
                    result = launcher.launch(ident or data.get("target"), setup=bool(data.get("setup")))
                elif path == "/api/updates":
                    result = launcher.check_updates(auto=bool(data.get("apply")))
                elif path == "/api/launcher-update":
                    result = launcher.stage_launcher_update()
                elif path == "/api/check-launcher":
                    result = launcher.check_launcher_release()
                elif path == "/api/launcher-permission":
                    marker = launcher.store.get("settings","launcher_update",{})
                    result = {"permitted":bool(marker.get("documents") and launcher.documents.permitted(marker["documents"],automatic=True)),
                              "auto":launcher.preferences()["auto_update"]}
                elif path == "/api/launcher-progress":
                    marker = launcher.store.get("settings","launcher_update",{})
                    result = launcher.store.put("settings","launcher_update",{**marker,"progress":max(0,min(100,float(data.get("progress",0)))),"message":str(data.get("message",""))[:500]})
                elif path == "/api/rollback":
                    result = launcher.rollback(ident or data.get("target"))
                elif path == "/api/cancel":
                    result = launcher.jobs.cancel(data.get("job_id", ""))
                elif path == "/api/dump":
                    result = launcher.dump_disc(data)
                elif path == "/api/verify":
                    result = launcher.verify_image(ident)
                elif path == "/api/pick":
                    mode = "folder" if data.get("mode") == "folder" else "file"
                    completed = subprocess.run([sys.executable, str(launcher.app_root / "tools/file_picker.py"), mode], capture_output=True, text=True, timeout=180)
                    if completed.returncode:
                        raise UserError("Nie udało się otworzyć okna wyboru. Możesz wkleić ścieżkę ręcznie.")
                    result = {"path": completed.stdout.strip()}
                else:
                    self.send_json({"error": "Nieznane żądanie."}, 404)
                    return
                self.send_json(result)
            except (UserError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
                self.send_json({"error": str(exc)}, 400)
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception:
                self.send_json({"error": "Nie udało się wykonać działania. Szczegóły są w terminalu."}, 500)
                import traceback
                traceback.print_exc()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

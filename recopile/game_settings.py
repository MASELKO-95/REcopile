"""Optional per-game settings, using each port's own configuration commands.

GPL-3.0-only. Copyright (C) 2026 MASELKO-95. Added 2026-10-20.
No settings command starts a game, downloads tools or edits a save.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .network import UserError
from .port_setup import python_command


def choice(key, label, values, *, advanced=False):
    return {"key": key, "label": label, "choices": values, "advanced": advanced}


PINYON_FIELDS = [
    choice("resolution_scale", "Rozdzielczość wewnętrzna", [1, 2, 3, 4]),
    choice("output_scaling", "Skalowanie obrazu", ["bilinear", "cas", "fsr", "fsr2", "fsr3", "dlss"]),
    choice("treasure_map", "Mapa skarbów", [True, False]),
    choice("game_preset", "Profil grafiki gry", ["ultra_low_30", "low_spec_60", "balanced_40", "performance_120", "quality_60"]),
    choice("anisotropy", "Filtrowanie anizotropowe", [0, 4, 8, 16], advanced=True),
    choice("post_effect", "Wygładzanie obrazu", ["none", "fxaa", "fxaa_extreme"], advanced=True),
    choice("presentation_fps", "Limit prezentacji FPS", [0, 30, 60, 120, 240], advanced=True),
    {"key": "render_fps", "label": "Limit renderowania FPS", "min": 0, "max": 240, "advanced": True},
    choice("disable_bloom", "Wyłącz bloom", [True, False], advanced=True),
    choice("disable_motion_blur", "Wyłącz rozmycie ruchu", [True, False], advanced=True),
    choice("disable_depth_of_field", "Wyłącz głębię ostrości", [True, False], advanced=True),
    choice("preset", "Profil rozdzielczości", ["custom", "shipping_1x", "experimental_2x", "experimental_3x"], advanced=True),
    choice("graphics_api", "API grafiki", ["vulkan"], advanced=True),
]

# Only options present in this FH2 runtime are offered. In particular, its
# current Linux build has no FidelityFX runtime: FSR is not advertised here.
FH2_FIELDS = [
    choice("resolution_scale", "Rozdzielczość wewnętrzna", [1, 2, 3, 4]),
    choice("vsync", "Synchronizacja pionowa", [True, False]),
    choice("post_effect", "Wygładzanie obrazu", ["none", "fxaa", "fxaa_extreme"]),
    choice("anisotropy", "Filtrowanie anizotropowe", [0, 4, 8, 16]),
]
FH2_DEFAULTS = {"resolution_scale": 1, "vsync": True, "post_effect": "none", "anisotropy": 4}


def validate_values(values, fields):
    if not isinstance(values, dict): raise UserError("Niepoprawne ustawienia gry.")
    known = {field["key"]: field for field in fields}
    for key, value in values.items():
        field = known.get(key)
        if not field: raise UserError("Nieobsługiwane ustawienie gry: " + str(key))
        if "choices" in field:
            if not any(type(value) is type(item) and value == item for item in field["choices"]):
                raise UserError("Niepoprawna wartość ustawienia: " + key)
        elif type(value) is not int or not field["min"] <= value <= field["max"]:
            raise UserError("Niepoprawna wartość ustawienia: " + key)
    return values


class GameSettings:
    def __init__(self, launcher): self.launcher = launcher

    def driver(self, install):
        source = install.get("source_id")
        if source in {"pinyon", "pinyon-linux"}:
            try: root = self.launcher.port_setup.root(install)
            except (KeyError, UserError): return None
            if source == "pinyon-linux" and (root / "tools/linux_support.py").is_file(): return "pinyon-legacy"
            if (root / "tools/pinyon.py").is_file(): return "pinyon"
        if source == "fh2-recomp-maselko" and install.get("local_executable") and install.get("engine_root"):
            return "fh2"
        return None

    def information(self, game):
        install = game.get("install") or {}
        if not install or (install.get("adapter") == "steam" and not install.get("local_executable")): return None
        return {"driver": self.driver(install) or "launch", "optional": True}

    def fields(self, driver):
        if driver == "pinyon": return PINYON_FIELDS
        if driver == "fh2": return FH2_FIELDS
        if driver == "pinyon-legacy":
            result = [dict(field) for field in PINYON_FIELDS if field["key"] not in {"game_preset", "preset", "graphics_api", "disable_bloom"}]
            for field in result:
                if field["key"] == "output_scaling": field["choices"] = ["bilinear", "cas", "fsr"]
                if field["key"] == "anisotropy": field["choices"] = [4, 8, 16]
            result += [choice("controls", "Sterowanie", ["controller", "pc-camera", "pc-steering"]),
                       choice("trainer", "Trainer", [True, False], advanced=True)]
            return result
        return []

    def upstream(self, install, driver, operation, values):
        root = self.launcher.port_setup.root(install)
        state = Path(install.get("pinyon_state_root") or Path(install["user_root"]) / ("preview" if driver == "pinyon-legacy" else "pinyon"))
        if driver == "pinyon":
            command = [python_command(root), str(root / "tools/pinyon.py"), "hardware"] if operation == "hardware" else [python_command(root), str(root / "tools/pinyon.py"), "config", operation, "--state-root", str(state)]
        else:
            command = [python_command(root), str(root / "tools/linux_support.py"), "graphics", "--action", operation, "--state-root", str(state)]
        for key, value in values.items():
            command += ["--" + key.replace("_", "-"), str(value).lower() if isinstance(value, bool) else str(value)]
        command.append("--json")
        try:
            process = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UserError("Nie udało się odczytać ustawień projektu: " + str(error)) from error
        try: result = json.loads(process.stdout)
        except ValueError: result = {}
        if not isinstance(result, dict): result = {}
        if process.returncode or result.get("error"):
            raise UserError(str(result.get("error") or process.stderr or "Narzędzie projektu nie zwróciło ustawień.")[-1800:])
        if operation == "hardware": return result
        if driver == "pinyon-legacy":
            # The owner's archived Linux patch returns TOML for reads. Its own
            # CLI still performs all writes, backups and schema checks.
            import tomllib
            try: config = tomllib.loads(result.get("config", ""))
            except ValueError as error: raise UserError("Niepoprawny plik konfiguracji portu.") from error
            result["settings"] = {
                "resolution_scale": config.get("draw_resolution_scale_x", 1),
                "output_scaling": config.get("present_effect", "bilinear"),
                "treasure_map": config.get("pinyon_shift_dlc_treasure_map", True),
                "anisotropy": {3: 4, 4: 8, 5: 16}.get(config.get("anisotropic_override"), 4),
                "post_effect": config.get("swap_post_effect", "none"),
                "disable_motion_blur": config.get("disable_motion_blur", True),
                "disable_depth_of_field": config.get("disable_depth_of_field", True),
                "controls": "controller" if not config.get("mnk_mode", True) else "pc-steering" if config.get("mnk_mouse_steering") else "pc-camera",
                "trainer": config.get("pinyon_shift_cheats", False),
                "host_present_fps_limit": config.get("host_present_fps_limit", 0),
                "fh1_render_fps_limit": config.get("pinyon_shift_fh1_render_fps_limit", 0),
            }
            result.pop("config", None)
        if not isinstance(result.get("settings"), dict): raise UserError("Narzędzie projektu nie zwróciło ustawień.")
        result["settings"]["presentation_fps"] = result["settings"].get("host_present_fps_limit", 0)
        result["settings"]["render_fps"] = result["settings"].get("fh1_render_fps_limit", 0)
        return result

    def request(self, ident, data):
        operation = data.get("operation", "get")
        if operation not in {"get", "apply", "reset", "restore", "hardware"}: raise UserError("Nieznana operacja ustawień.")
        values = data.get("values", {})
        with self.launcher.process_lock:
            game = self.launcher.require_game(ident)
            install = self.launcher.store.get("installs", ident)
            if not install or not self.information({**game, "install": install}): raise UserError("Najpierw podłącz lub zainstaluj tę grę.")
            driver = self.driver(install)
            fields = self.fields(driver)
            validate_values(values, fields)
            if operation != "apply" and values: raise UserError("Ta operacja nie przyjmuje zmian ustawień.")
            launch = None
            if "launch" in data:
                if operation != "apply": raise UserError("Opcje uruchamiania można zapisać tylko przez Zapisz.")
                launch = self.validate_launch(data["launch"], install)
            if ident in self.launcher.running and operation not in {"get", "hardware"}: raise UserError("Zamknij grę przed zmianą ustawień.")
            if operation not in {"get", "hardware"} and any(job["target"] == ident and job["kind"] in {"prepare", "install"} and job["status"] in {"queued", "running"} for job in self.launcher.jobs.list()):
                raise UserError("Poczekaj na zakończenie przygotowania gry.")
            if operation == "hardware" and driver != "pinyon": raise UserError("Ten projekt nie udostępnia raportu sprzętu.")
            if driver in {"pinyon", "pinyon-legacy"}:
                result = self.upstream(install, driver, operation, values)
                if operation == "hardware": return {"hardware": result}
            else:
                if operation == "restore": raise UserError("Ten projekt nie udostępnia przywracania konfiguracji.")
                defaults = FH2_DEFAULTS if driver == "fh2" else {}
                settings = self.launcher.store.get("settings", "graphics:" + ident, defaults)
                settings = {**defaults, **settings}
                if operation == "apply": settings.update(values)
                elif operation == "reset": settings = dict(defaults)
                if operation != "get": self.launcher.store.put("settings", "graphics:" + ident, settings)
                result = {"settings": settings, "restart_required": operation != "get"}
            if launch is not None:
                self.launcher.store.put("settings", "launch:" + ident, launch)
            return {**result, "driver": driver or "launch", "fields": fields,
                    "can_restore": driver in {"pinyon", "pinyon-legacy"}, "can_hardware": driver == "pinyon",
                    "launch": self.launcher.store.get("settings", "launch:" + ident, {"arguments": []}),
                    "can_compatibility": bool(install.get("local_executable") and install.get("local_system") == "windows" and self.launcher.system_key() == "linux"),
                    "runner": install.get("runner", "proton"), "proton_path": install.get("proton_path", "")}

    def validate_launch(self, value, install):
        if not isinstance(value, dict) or set(value) - {"arguments", "runner", "proton_path"}: raise UserError("Niepoprawne opcje uruchamiania.")
        arguments = value.get("arguments", [])
        if not isinstance(arguments, list) or len(arguments) > 128 or any(not isinstance(arg, str) or not arg or len(arg) > 4096 or "\0" in arg for arg in arguments): raise UserError("Niepoprawne argumenty uruchamiania.")
        result = {"arguments": arguments}
        if "runner" in value or "proton_path" in value:
            if not (install.get("local_executable") and install.get("local_system") == "windows" and self.launcher.system_key() == "linux"): raise UserError("Zgodność dotyczy programów Windows na Linuxie.")
            if value.get("runner") not in {"proton", "wine"}: raise UserError("Wybierz Proton albo Wine.")
            if not isinstance(value.get("proton_path", ""), str) or len(value.get("proton_path", "")) > 4096: raise UserError("Niepoprawna ścieżka do Protona.")
            result.update(runner=value["runner"], proton_path=value.get("proton_path", ""))
        return result

    def launch_install(self, ident, install):
        selected = self.launcher.store.get("settings", "launch:" + ident, {})
        return {**install, **{key: selected[key] for key in ("runner", "proton_path") if key in selected}}

    def arguments(self, ident, install):
        args = []
        if self.driver(install) == "fh2":
            settings = self.launcher.store.get("settings", "graphics:" + ident, {})
            validate_values(settings, FH2_FIELDS)
            for key, value in settings.items():
                if key == "resolution_scale": args += [f"--draw_resolution_scale_x={value}", f"--draw_resolution_scale_y={value}"]
                elif key == "anisotropy": args.append("--anisotropic_override=" + str({0: -1, 4: 3, 8: 4, 16: 5}[value]))
                else: args.append("--" + {"post_effect": "swap_post_effect"}.get(key, key) + "=" + str(value).lower())
        selected = self.launcher.store.get("settings", "launch:" + ident, {"arguments": []})
        args += self.validate_launch(selected, install)["arguments"]
        return args

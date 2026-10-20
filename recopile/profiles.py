from __future__ import annotations
import base64
import re
import time
import uuid
from pathlib import Path
from .network import UserError

DEFINITIONS = [
    {"id":"first-launch","name":"Pierwsza podróż","description":"Uruchomiono pierwszą grę z launchera.","points":20,"metric":"launches","threshold":1},
    {"id":"five-games","name":"Odkrywca","description":"Uruchomiono pięć różnych gier.","points":50,"metric":"games","threshold":5},
    {"id":"one-hour","name":"Dobra godzina","description":"Godzina łącznego czasu uruchomionych gier.","points":30,"metric":"seconds","threshold":3600},
    {"id":"ten-hours","name":"Stały bywalec","description":"Dziesięć godzin łącznego czasu uruchomionych gier.","points":100,"metric":"seconds","threshold":36000},
]

class Profiles:
    def __init__(self, store): self.store = store

    def active(self):
        ident = self.store.get("settings", "preferences")["active_profile"]
        return self.store.get("profiles", ident) or self.store.get("profiles", "local")

    def create(self, name):
        name = str(name).strip()
        if not 1 <= len(name) <= 40:
            raise UserError("Nazwa profilu musi mieć od 1 do 40 znaków.")
        profile = {"id": uuid.uuid4().hex[:16], "name": name, "created_at": time.time()}
        self.store.put("profiles", profile["id"], profile)
        return profile

    def switch(self, ident):
        profile = self.store.get("profiles", ident)
        if not profile: raise UserError("Nie znaleziono profilu.")
        prefs = self.store.get("settings", "preferences")
        self.store.put("settings", "preferences", {**prefs, "active_profile": ident, "profile_name": profile["name"]})
        return self.summary(ident)

    def rename(self, name):
        profile = self.active()
        name = str(name).strip()
        if not 1 <= len(name) <= 40: raise UserError("Niepoprawna nazwa profilu.")
        self.store.put("profiles", profile["id"], {**profile, "name": name})

    def record(self, profile_id, game, seconds, exit_code):
        if seconds < 1 and exit_code:
            return
        ident = profile_id + ":" + game["id"]
        old = self.store.get("profile_stats", ident, {})
        self.store.put("profile_stats", ident, {"id": ident, "profile_id": profile_id, "game_id": game["id"], "title": game["title"],
            "platform": game["platform"], "seconds": old.get("seconds", 0) + max(0, int(seconds)), "launches": old.get("launches", 0) + 1,
            "last_played": time.time(), "last_exit_code": exit_code})
        summary = self.summary(profile_id)
        metrics = {"launches": summary["launches"], "games": len(summary["games"]), "seconds": summary["seconds"]}
        for definition in DEFINITIONS:
            unlock_id = profile_id + ":" + definition["id"]
            if metrics[definition["metric"]] >= definition["threshold"] and not self.store.get("achievements", unlock_id):
                self.store.put("achievements", unlock_id, {**definition, "id": unlock_id, "achievement_id": definition["id"], "profile_id": profile_id, "unlocked_at": time.time(), "origin": "launcher"})

    def summary(self, ident=None):
        profile = self.store.get("profiles", ident) if ident else self.active()
        if not profile: raise UserError("Nie znaleziono profilu.")
        games = sorted([g for g in self.store.list("profile_stats") if g["profile_id"] == profile["id"]], key=lambda g:g["seconds"], reverse=True)
        for entry in games:
            game=self.store.game(entry['game_id'])
            entry['game_available']=bool(game)
            install=self.store.decorate(game).get('install') if game else None
            entry['can_launch']=bool(install and (install.get('ready') or (install.get('experimental') and install.get('local_executable'))))
            entry['launch_method']='steam' if install and install.get('adapter')=='steam' and not install.get('local_executable') else 'local'
            # Launcher activity badges are separate from achievements awarded by
            # an individual game. An unconnected source has no known count.
            entry['game_achievements']={'status':'not_connected','unlocked':None,'total':None}
        unlocked = [a for a in self.store.list("achievements") if a["profile_id"] == profile["id"]]
        return {"profile": profile, "games": games, "seconds": sum(g["seconds"] for g in games), "launches": sum(g["launches"] for g in games),
                "achievements": unlocked, "definitions": DEFINITIONS, "points": sum(a["points"] for a in unlocked), "generated_at": time.time()}

    def export_png(self):
        from PIL import Image, ImageDraw, ImageFont
        summary = self.summary()
        language = self.store.get('settings','preferences',{}).get('language','en')
        labels = {
            'pl':['Twoje gry. Twoje historie.','czasu uruchomionych gier','różnych gier','odznak launchera','punktów profilu','NAJCZĘŚCIEJ URUCHAMIANE','Jeszcze bez zarejestrowanej aktywności. Nowa przygoda przed Tobą.','Profil lokalny • Dane zadeklarowane przez launcher'],
            'en':['Your games. Your stories.','time in launched games','different games','launcher badges','profile points','MOST PLAYED','No recorded activity yet. Your next adventure awaits.','Local profile • Activity recorded by the launcher'],
            'hu':['A játékaid. A történeteid.','elindított játékok ideje','különböző játék','indítójelvény','profilpont','LEGGYAKRABBAN JÁTSZOTT','Még nincs rögzített tevékenység. Új kaland vár rád.','Helyi profil • Az indító által rögzített tevékenység'],
        }.get(language)
        if labels is None: labels = ['Your games. Your stories.','time in launched games','different games','launcher badges','profile points','MOST PLAYED','No recorded activity yet. Your next adventure awaits.','Local profile • Activity recorded by the launcher']
        font_dir = self.store.app_root / "frontend/dist/client/assets/fonts"
        def font(size, heading=False):
            path = font_dir / ("barlow-condensed-semibold.ttf" if heading else "inter.ttf")
            return ImageFont.truetype(str(path), size)
        canvas = Image.new("RGB", (1280, 840), "#101114")
        draw = ImageDraw.Draw(canvas)
        draw.text((58, 42), "RE:COPILE", fill="#a68beb", font=font(42, True))
        draw.text((58, 123), summary["profile"]["name"][:40], fill="#f0eaf7", font=font(62, True))
        draw.text((58, 205), labels[0], fill="#b3a7c3", font=font(22))
        metrics = [(f"{summary['seconds']/3600:.1f} h", labels[1]), (str(len(summary["games"])), labels[2]), (str(len(summary["achievements"])), labels[3]), (str(summary["points"]), labels[4])]
        for index, (value, label) in enumerate(metrics):
            x = 58 + index * 292
            draw.rounded_rectangle((x, 269, x+270, 382), 10, fill="#1d1927", outline="#433153", width=1)
            draw.text((x+19, 281), value, font=font(44, True), fill="#c3a7ff")
            draw.text((x+19, 344), label, font=font(15), fill="#aaa0b8")
        draw.text((58, 425), labels[5], fill="#a28eb8", font=font(17))
        for index, game in enumerate(summary["games"][:5]):
            y = 478 + index*49
            title = game["title"][:65] + ("…" if len(game["title"]) > 65 else "")
            draw.text((58, y), f"{index+1}.  {title}", fill="#ddd4e8", font=font(22, True))
            draw.text((1040, y), f"{game['seconds']/3600:.1f} h", fill="#b8a0da", font=font(22, True))
        if not summary["games"]:
            draw.text((58, 483), labels[6], fill="#a294b1", font=font(21))
        draw.line((58, 767, 1222, 767), fill="#393040", width=1)
        date = time.strftime("%Y-%m-%d", time.localtime(summary["generated_at"]))
        draw.text((58, 790), labels[7], fill="#9b89ac", font=font(14))
        draw.text((1090, 790), date, fill="#9b89ac", font=font(14))
        output = self.store.root / "reports"
        output.mkdir(exist_ok=True)
        name = f"Recopile-{summary['profile']['id']}-{date}.png"
        path = output / name
        canvas.save(path)
        return {"filename": name, "mime": "image/png", "base64": base64.b64encode(path.read_bytes()).decode(), "summary": summary}

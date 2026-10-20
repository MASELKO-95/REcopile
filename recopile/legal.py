"""Versioned upstream documentation and explicit download consent."""
from __future__ import annotations
import base64
import hashlib
import json
import re
import time
from urllib.parse import quote, urlparse
from .network import UserError, fetch_json, validate_repo

SPONSOR_URL = "https://github.com/sponsors/MASELKO-95"
MAX_DOCUMENT = 256_000

def decode_document(payload, fallback_url):
    if not isinstance(payload, dict) or payload.get("encoding") != "base64" or payload.get("size", 0) > MAX_DOCUMENT:
        raise UserError("Dokument projektu jest za duży lub ma nieobsługiwany format.")
    raw = base64.b64decode(payload.get("content", ""), validate=False)
    if len(raw) > MAX_DOCUMENT: raise UserError("Dokument projektu przekracza limit 256 KB.")
    text = raw.decode("utf-8", errors="replace")
    return {"name":payload.get("name", "Dokument"), "text":text,
            "url":payload.get("html_url", fallback_url), "sha256":hashlib.sha256(raw).hexdigest(), "available":True}

def funding_links(text):
    """Read common FUNDING.yml scalar/list entries without executing YAML tags."""
    links = []
    templates = {"github":"https://github.com/sponsors/", "patreon":"https://www.patreon.com/",
                 "ko_fi":"https://ko-fi.com/", "open_collective":"https://opencollective.com/",
                 "buy_me_a_coffee":"https://www.buymeacoffee.com/", "liberapay":"https://liberapay.com/"}
    for line in text.splitlines():
        match = re.match(r"^([a-z_]+):\s*(.*?)\s*(?:\s+#.*)?$", line)
        if not match: continue
        key, value = match.groups()
        if key not in {*templates, "custom"}: continue
        values = re.findall(r"https://[^\s\]\[,'\"]+", value) if key == "custom" else [v.strip(" []'\"") for v in value.split(",")]
        for item in values:
            if not item or item in {"null", "~"}: continue
            if key != "custom" and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", item): continue
            url = item if key == "custom" else templates[key] + item
            parsed = urlparse(url)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and parsed.port in (None, 443):
                links.append({"label": "GitHub Sponsors" if key == "github" else key.replace("_", " ").title(), "url":url})
    return list({link["url"]:link for link in links}.values())[:12]

class ProjectDocuments:
    def __init__(self, store): self.store = store

    def get(self, source, release, refresh=False):
        repo = validate_repo(source.get("documentation_repo", source["repo"]))
        version = release["version"]
        key = repo + "@" + version + ":" + release["asset"]["name"]
        cache = self.store.get("settings", "documents:" + key)
        if cache and not refresh: return cache
        base = "https://api.github.com/repos/" + repo
        doc_ref = version
        if source.get("documentation_repo"):
            doc_ref = version[6:] if re.fullmatch(r"build-[a-f0-9]{40}", version) else source.get("documentation_ref", "HEAD")
            if not re.fullmatch(r"[a-f0-9]{40}", doc_ref):
                doc_ref = fetch_json(base + "/commits/" + quote(doc_ref, safe=""))["sha"]
        ref = "?ref=" + quote(doc_ref, safe="")
        result = {"repo":repo, "source_id":source.get("id"), "name":source.get("name", repo), "version":version,
                  "release_url":release["url"], "release_notes":release.get("notes", ""), "asset_name":release["asset"]["name"],
                  "asset_size":release["asset"]["size"], "fetched_at":time.time(), "funding":[], "documentation_ref":doc_ref}
        for kind, endpoint in [("readme", "/readme"), ("license", "/license")]:
            fallback = "https://github.com/" + repo + ("/tree/" + quote(doc_ref, safe="") if kind == "license" else "/blob/" + quote(doc_ref, safe="") + "/README.md")
            try:
                try:
                    payload = fetch_json(base + endpoint + ref)
                except UserError:
                    if kind != 'license': raise
                    # GitHub's license detector can miss custom licenses. Read the
                    # actual file at the same release ref before declaring it absent.
                    payload = fetch_json(base + '/contents/LICENSE' + ref)
                result[kind] = decode_document(payload, fallback)
                if kind == "license": result["license"]["spdx"] = payload.get("license", {}).get("spdx_id", "")
            except UserError as exc:
                # Missing upstream documents are stated explicitly, never invented.
                # Network/permission failures cannot silently permit unattended updates.
                result[kind] = {"available":False, "url":fallback, "text":"", "sha256":"", "error":str(exc)}
        try:
            funding = decode_document(fetch_json(base + "/contents/.github/FUNDING.yml" + ref), "https://github.com/" + repo + "/blob/" + quote(version, safe="") + "/.github/FUNDING.yml")
            result["funding"] = funding_links(funding["text"])
            result["funding_url"] = funding["url"]
        except UserError: pass
        result["fingerprint"] = hashlib.sha256(json.dumps({"repo":repo, "version":version, "asset":result["asset_name"], "license":result["license"]["sha256"], "readme":result["readme"]["sha256"]}, sort_keys=True).encode()).hexdigest()
        self.store.put("settings", "documents:" + key, result)
        return result

    def accept(self, documents, fingerprint, auto=False, *, license_accepted=False, license_hash=None):
        if fingerprint != documents["fingerprint"]: raise UserError("Dokumentacja wydania się zmieniła. Otwórz informacje ponownie.")
        license_doc = documents['license']
        if not license_doc.get('available') or not license_doc.get('text', '').strip() or not license_doc.get('sha256'):
            raise UserError('Licencja tego wydania jest niedostępna. Instalacja wymaga dostępnej licencji projektu.')
        if license_accepted is not True or license_hash != license_doc['sha256']:
            raise UserError('Otwórz licencję projektu i osobno zaakceptuj jej warunki przed instalacją.')
        accepted = {"repo":documents["repo"], "version":documents["version"], "fingerprint":fingerprint,
                    "license_hash":license_doc['sha256'], "license_accepted":True, "auto":bool(auto), "accepted_at":time.time()}
        self.store.put("settings", "consent:" + documents["repo"], accepted)
        return accepted

    def permitted(self, documents, automatic=False):
        accepted = self.store.get("settings", "consent:" + documents["repo"], {})
        license_doc = documents['license']
        if (not license_doc.get('available') or not license_doc.get('text', '').strip()
                or not license_doc.get('sha256') or accepted.get('license_accepted') is not True
                or accepted.get('license_hash') != license_doc['sha256']):
            return False
        if accepted.get("fingerprint") == documents["fingerprint"]:
            return not automatic or accepted.get("auto", False)
        # New versions need visible prior notice and an unchanged, available license.
        seen = self.store.get("settings", "seen:" + documents["fingerprint"], False)
        return bool(automatic and seen and accepted.get("auto") and documents["license"]["available"]
                    and documents["readme"]["available"] and accepted.get("license_hash") == documents["license"]["sha256"])

    def seen(self, fingerprint):
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint): raise UserError("Niepoprawna informacja o wydaniu.")
        self.store.put("settings", "seen:" + fingerprint, time.time())
        return {"ok":True}

    def app_notice(self, version):
        prefs = self.store.get("settings", "preferences")
        license_path = self.store.app_root / "LICENSE"
        privacy_path = self.store.app_root / "PRIVACY.md"
        license_text = license_path.read_text(encoding="utf-8") if license_path.is_file() else "Licencja nie została dołączona do tego wydania."
        license_hash = hashlib.sha256(license_text.encode()).hexdigest()
        distribution_path = self.store.app_root / "data/distribution.json"
        distribution = json.loads(distribution_path.read_text()) if distribution_path.is_file() else {}
        first = not prefs.get("onboarding_complete")
        updated = not first and prefs.get("last_notice_version") != version
        return {"required": first or updated or prefs.get('app_license_accepted') is not True or prefs.get("accepted_app_license") != license_hash,
                "first_run":first,
                "updated":updated, "license":license_text, "license_hash":license_hash,
                "license_name":"GNU GPLv3", "author":"MASELKO-95", "author_url":"https://github.com/MASELKO-95",
                "original_url":"https://github.com/" + distribution["repo"] if distribution.get("repo") else None,
                "privacy":privacy_path.read_text() if privacy_path.is_file() else "Informacja o prywatności nie została dołączona do tego wydania.",
                "sponsor_url":SPONSOR_URL, "version":version}

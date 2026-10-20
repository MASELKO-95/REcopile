"""Declarative mod packages. No executable installation scripts are run."""
from __future__ import annotations
import hashlib
import base64
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from .network import UserError, safe_member

def validate_manifest(value):
    if not isinstance(value,dict) or value.get('schema_version')!=1: raise UserError('Nieobsługiwana wersja manifestu moda.')
    for field in ['id','version','game_id']:
        if not isinstance(value.get(field),str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',value[field]) or value[field] in {'.','..'}: raise UserError('Niepoprawny identyfikator lub wersja moda.')
    for field in ['name','author','license']:
        if not isinstance(value.get(field),str) or not 1<=len(value[field])<=200: raise UserError('Manifest wymaga nazwy, autora i licencji.')
    if not isinstance(value.get('supported_versions'),list) or not value['supported_versions'] or any(not isinstance(v,str) or not 1<=len(v)<=100 or v=='*' for v in value['supported_versions']): raise UserError('Podaj konkretne obsługiwane wersje portu. Nie używaj gwiazdki.')
    if not isinstance(value.get('systems'),list) or not value['systems'] or any(v not in ['linux','windows'] for v in value['systems']): raise UserError('Podaj systemy moda: linux, windows.')
    if not isinstance(value.get('files'),list) or not 1<=len(value['files'])<=2000: raise UserError('Niepoprawna lista plików moda.')
    names=set()
    for file in value['files']:
        if not isinstance(file,dict) or not isinstance(file.get('source'),str) or not isinstance(file.get('target'),str): raise UserError('Niepoprawny wpis pliku.')
        if not file['source'].startswith('payload/') or not file['target'] or file['target'].endswith('/') or file['target'] in {'.','..'}: raise UserError('Pliki muszą pochodzić z payload/ i mieć docelową nazwę.')
        safe_member(file['source'],Path('/tmp/recopile-mod-validation'))
        safe_member(file['target'],Path('/tmp/recopile-mod-validation'))
        if file['target'].casefold() in names: raise UserError('Mod ma kolidujące nazwy plików.')
        names.add(file['target'].casefold())
        if not re.fullmatch(r'[a-f0-9]{64}',file.get('sha256','')): raise UserError('Każdy plik moda wymaga SHA-256.')
    return value

class Workshop:
    def __init__(self,launcher): self.launcher=launcher; self.store=launcher.store

    @staticmethod
    def _hash(path):
        result=hashlib.sha256()
        with Path(path).open('rb') as stream:
            while block:=stream.read(1024*1024): result.update(block)
        return result.hexdigest()

    def _idle(self,game_id):
        if any(game['id']==game_id for game in self.launcher.active_processes()) or any(job['target']==game_id and job['status'] in {'queued','running'} for job in self.launcher.jobs.list()):
            raise UserError('Zamknij grę i poczekaj na instalację portu przed zmianą modów.')

    def catalog(self):
        cache=self.store.get('settings','workshop_catalog')
        return cache or json.loads((self.store.app_root/'data/workshop.json').read_text())

    def state(self):
        installs=self.store.list('installs')
        games=[self.store.decorate(self.store.game(i['id'])) for i in installs if not i['id'].startswith('engine-') and self.store.game(i['id'])]
        return {'installed':self.store.list('mods'),'catalog':self.catalog(),'games':games}

    def template(self,game_id):
        game=self.launcher.require_game(game_id)
        install=self.store.get('installs',game_id,{})
        manifest={'schema_version':1,'id':'moj-mod','name':'Mój mod','author':self.launcher.profiles.active()['name'],
            'version':'1.0.0','game_id':game_id,'source_id':install.get('source_id',''),'supported_versions':[install.get('version','local')],
            'systems':['linux','windows'],'license':'LicenseRef-Author-Choose','files':[]}
        readme='# Szablon moda dla '+game['title']+'\n\nTo szablon, nie gotowy mod. Dodaj własne pliki do payload/, wybierz własną licencję w LICENSE i nazwij autora. Dopasuj wersję portu oraz systemy. Zbuduj paczkę narzędziem tools/build_mod.py z repozytorium Recopile.\n\nGracz otwiera paczkę .recopilemod w Recopile, przegląda README, licencję i pliki, potem potwierdza instalację. Skrypty nie są wykonywane z paczki. Aktywacja wymaga adaptera folderu modów wskazanego zgodnie z README portu.\n\nNie dołączaj ISO, BIOS-u ani oryginalnych zasobów gry.\n'
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            z.writestr('README.md',readme)
            z.writestr('LICENSE','Uzupełnij rzeczywistą licencję swoich plików przed publikacją. Ta paczka jest szablonem.\n')
            z.writestr('payload/.keep','')
            z.writestr('discord-post.md','# '+game['title']+' — nazwa moda\nAutor: ...\nWersja moda: ...\nWersja portu: ...\nSystem: Linux / Windows\nOpis zmian: ...\nREADME i licencja: ...\nPobierz: link do .recopilemod w GitHub Releases\nInstalacja: otwórz paczkę w Recopile i przejrzyj informacje.\n')
        return {'filename':'Recopile-workshop-template.zip','mime':'application/zip','base64':base64.b64encode(stream.getvalue()).decode()}

    def inspect(self,path):
        path=Path(path).expanduser().resolve()
        if not path.is_file() or path.stat().st_size>256*1024**2: raise UserError('Wskaż paczkę .recopilemod / ZIP do 256 MB.')
        if not zipfile.is_zipfile(path): raise UserError('Paczka moda musi być archiwum ZIP z manifest.json, README.md, LICENSE i payload/.')
        with zipfile.ZipFile(path) as z:
            members=z.infolist()
            if len(members)>10000 or sum(m.file_size for m in members)>512*1024**2: raise UserError('Paczka moda jest za duża po rozpakowaniu.')
            names=[m.filename for m in members]
            if len(names)!=len(set(names)): raise UserError('Paczka zawiera powtórzone pliki.')
            for m in members:
                safe_member(m.filename,self.store.root/'mod-validation')
                if (m.external_attr>>16)&0o170000==0o120000: raise UserError('Dowiązania w paczkach modów są niedozwolone.')
            def text(name):
                if name not in names or z.getinfo(name).file_size>256000: raise UserError('Paczka wymaga niewielkiego pliku '+name+'.')
                return z.read(name).decode('utf-8',errors='replace')
            manifest=validate_manifest(json.loads(text('manifest.json')))
            readme,license_text=text('README.md'),text('LICENSE')
            for file in manifest['files']:
                if file['source'] not in names: raise UserError('Brak pliku '+file['source'])
                with z.open(file['source']) as stream:
                    h=hashlib.sha256()
                    while block:=stream.read(1024*1024): h.update(block)
                if h.hexdigest()!=file['sha256']: raise UserError('Niezgodna suma pliku '+file['source'])
        game=self.launcher.require_game(manifest['game_id'])
        install=self.store.get('installs',game['id'])
        if not install: raise UserError('Najpierw podłącz lub zainstaluj grę, dla której powstał mod.')
        if manifest.get('source_id') and manifest['source_id']!=install.get('source_id'): raise UserError('Mod powstał dla innego portu tej gry.')
        if install.get('version','local') not in manifest['supported_versions']: raise UserError('Mod nie deklaruje zgodności z wersją '+install.get('version','local'))
        if self.launcher.system_key() not in manifest['systems']: raise UserError('Mod nie jest przeznaczony dla tego systemu.')
        source=self.store.get('sources',install.get('source_id',''),{})
        mod_root=source.get('mod_root','')
        target_root=safe_member(mod_root,Path(install['game_root'])) if mod_root else None
        if target_root and target_root.exists() and not target_root.is_dir(): raise UserError('Folder modów musi być katalogiem.')
        destinations=[]
        for file in manifest['files']:
            target=safe_member(file['target'],target_root) if target_root else None
            if target and target.exists() and not target.is_file(): raise UserError('Docelowy plik moda koliduje z katalogiem.')
            destinations.append({'file':file['target'],'exists':bool(target and target.exists()),'current_hash':self._hash(target) if target and target.is_file() else None})
        h=hashlib.sha256()
        with path.open('rb') as stream:
            while block:=stream.read(1024*1024): h.update(block)
        fingerprint=hashlib.sha256((h.hexdigest()+json.dumps(destinations,sort_keys=True)+install.get('version','local')+mod_root).encode()).hexdigest()
        return {'path':str(path),'manifest':manifest,'readme':readme,'license_text':license_text,
                'license_hash':hashlib.sha256(license_text.encode()).hexdigest(),'game':game['title'],'fingerprint':fingerprint,
                'targets':destinations,'can_activate':bool(mod_root),'mod_root':mod_root,
                'message':'Mod zostanie zainstalowany w folderze obsługiwanym przez port.' if mod_root else 'Port nie deklaruje adaptera modów. Paczka zostanie zapisana jako przygotowana; nie będzie aktywowana w grze.'}

    def install(self,path,fingerprint,trusted=False,overwrite=False,*,license_accepted=False,license_hash=None):
        with self.launcher.process_lock:
            return self._install(path,fingerprint,trusted,overwrite,license_accepted=license_accepted,license_hash=license_hash)

    def _install(self,path,fingerprint,trusted=False,overwrite=False,*,license_accepted=False,license_hash=None):
        if not trusted: raise UserError('Zapoznaj się z dokumentacją i potwierdź zaufanie do moda.')
        review=self.inspect(path)
        if review['fingerprint']!=fingerprint: raise UserError('Paczka, gra lub pliki docelowe zmieniły się. Przejrzyj instalację ponownie.')
        if not review['license_text'].strip(): raise UserError('Licencja moda jest pusta. Instalacja wymaga dostępnej licencji projektu.')
        if license_accepted is not True or license_hash!=review['license_hash']:
            raise UserError('Otwórz licencję projektu i osobno zaakceptuj jej warunki przed instalacją.')
        m=review['manifest']; ident=m['game_id']+':'+m['id']
        self._idle(m['game_id'])
        if self.store.get('mods',ident): raise UserError('Ten mod jest już zainstalowany. Usuń go przed instalacją innej wersji.')
        if any(t['exists'] for t in review['targets']) and not overwrite: raise UserError('Mod zmieni istniejące pliki. Potwierdź ich nadpisanie po przejrzeniu listy.')
        install=self.store.get('installs',m['game_id'])
        base=safe_member('mods/managed/'+m['id']+'/'+m['version'],Path(install['game_root']))
        if base.exists(): raise UserError('Folder tej wersji moda już istnieje.')
        # Conflicting active mods need removal; never overwrite another mod's files.
        for old in self.store.list('mods'):
            if old['game_id']==m['game_id'] and old.get('active') and set(f['target'] for f in old['files'])&set(f['target'] for f in m['files']): raise UserError('Inny aktywny mod używa tych plików. Najpierw go usuń.')
        base.mkdir(parents=True)
        copies=[]
        try:
            with zipfile.ZipFile(path) as z:
                for file in m['files']:
                    staged=safe_member(file['source'],base)
                    staged.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(file['source']) as src,staged.open('xb') as dst: shutil.copyfileobj(src,dst,1024*1024)
                    if self._hash(staged)!=file['sha256']: raise UserError('Paczka zmieniła się po przejrzeniu. Przejrzyj ją ponownie.')
                    if review['can_activate']:
                        root=Path(install['game_root'])/review['mod_root']; target=safe_member(file['target'],root)
                        if not target.resolve().is_relative_to(Path(install['game_root']).resolve()): raise UserError('Folder modów prowadzi poza bibliotekę.')
                        target.parent.mkdir(parents=True,exist_ok=True)
                        backup=safe_member(file['target'],base/'backup')
                        if target.exists(): backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
                        copies.append((target,backup if backup.is_file() else None))
                        temp=target.with_name(target.name+'.recopile-tmp')
                        with temp.open('xb') as dst,staged.open('rb') as src: shutil.copyfileobj(src,dst,1024*1024)
                        temp.replace(target)
            (base/'README.md').write_text(review['readme'],encoding='utf-8'); (base/'LICENSE').write_text(review['license_text'],encoding='utf-8')
            (base/'manifest.json').write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding='utf-8')
            record={'id':ident,'mod_id':m['id'],'name':m['name'],'author':m['author'],'version':m['version'],'game_id':m['game_id'],
                    'port_version':install.get('version','local'),'root':str(base),'target_root':str(Path(install['game_root'])/review['mod_root']),
                    'active':review['can_activate'],'files':m['files'],'installed_at':time.time(),'message':review['message'],
                    'license_accepted':True,'license_hash':review['license_hash']}
            return self.store.put('mods',ident,record)
        except Exception:
            for target,backup in reversed(copies):
                if backup: shutil.copy2(backup,target)
                else: target.unlink(missing_ok=True)
            shutil.rmtree(base,ignore_errors=True)
            raise

    def remove(self,ident):
        with self.launcher.process_lock:
            return self._remove(ident)

    def _remove(self,ident):
        mod=self.store.get('mods',ident)
        if not mod: raise UserError('Nie znaleziono moda.')
        self._idle(mod['game_id'])
        install=self.store.get('installs',mod['game_id'])
        if not install: raise UserError('Nie znaleziono instalacji gry.')
        game_root=Path(install['game_root']).resolve()
        if not Path(mod['root']).resolve().is_relative_to(game_root) or not Path(mod['target_root']).resolve().is_relative_to(game_root):
            raise UserError('Folder moda prowadzi poza bibliotekę.')
        if mod['active']:
            # Verify all targets before changing any of them.
            for file in mod['files']:
                target=safe_member(file['target'],Path(mod['target_root']))
                if not target.is_file() or self._hash(target)!=file['sha256']: raise UserError('Pliki moda zmieniono po instalacji. Nie usuwamy ani nie nadpisujemy ich automatycznie.')
            for file in mod['files']:
                target=safe_member(file['target'],Path(mod['target_root'])); backup=safe_member(file['target'],Path(mod['root'])/'backup')
                if backup.is_file(): shutil.copy2(backup,target)
                else: target.unlink()
        shutil.rmtree(mod['root']); self.store.delete('mods',ident)
        return {'ok':True,'message':'Usunięto mod; poprzednie pliki przywrócono, jeśli były zmieniane.'}

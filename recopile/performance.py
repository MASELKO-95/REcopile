"""Opt-in local MangoHud / PresentMon sessions and bounded CSV analysis.

No synthetic FPS, account data, serial numbers, uploads or global overlay settings.
Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-19.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .network import UserError

MAX_LOG = 32 * 1024 * 1024

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def hardware(base):
    value = {k:v for k,v in base.items() if k in {'system','architecture','os_version','cpu','gpu'}}
    value.update(ram_gb=None, gpu_memory_gb=None, driver=None, logical_cpus=os.cpu_count())
    try:
        if platform.system() == 'Linux':
            cpu = Path('/proc/cpuinfo').read_text(errors='replace')
            value['cpu'] = next((l.split(':',1)[1].strip() for l in cpu.splitlines() if l.startswith('model name')), value.get('cpu'))
            memory = Path('/proc/meminfo').read_text()
            value['ram_gb'] = round(int(next(l.split()[1] for l in memory.splitlines() if l.startswith('MemTotal:'))) / 1024**2, 2)
            if shutil.which('nvidia-smi'):
                result = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'], capture_output=True,text=True,timeout=4)
                if not result.returncode:
                    parts = next(csv.reader(result.stdout.splitlines()))
                    value.update(gpu=parts[0].strip(),gpu_memory_gb=round(float(parts[1])/1024,2),driver=parts[2].strip())
        elif platform.system() == 'Windows':
            script = '$c=Get-CimInstance Win32_Processor | Select-Object -First 1; $m=Get-CimInstance Win32_ComputerSystem; $g=Get-CimInstance Win32_VideoController | Select-Object -First 1; @{cpu=$c.Name;ram_gb=[math]::Round($m.TotalPhysicalMemory/1GB,2);gpu=$g.Name;driver=$g.DriverVersion} | ConvertTo-Json -Compress'
            result = subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=8)
            if not result.returncode: value.update(json.loads(result.stdout))
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired):
        pass
    return value

def analyse_csv(text, *, stream=None):
    """Parse raw logs, select one process/swapchain, and disclose the statistic basis."""
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_LOG:
        raise UserError('Log pomiaru jest zbyt duży (maks. 32 MB).')
    rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
    header_at = None
    for index, row in enumerate(rows[:40]):
        names = {c.strip().lower() for c in row}
        if 'fps' in names and 'frametime' in names or 'msbetweenpresents' in names or {'mscpubusy','mscpuwait'} <= names:
            header_at = index
            break
    if header_at is None: raise UserError('Nie znaleziono surowych próbek MangoHud / PresentMon w CSV.')
    names = [c.strip().lower() for c in rows[header_at]]
    mango = 'fps' in names and 'frametime' in names
    groups = {}
    rejected = 0
    for row in rows[header_at+1:]:
        if len(row) != len(names):
            rejected += 1
            continue
        item = dict(zip(names,row))
        key = 'MangoHud' if mango else '|'.join(item.get(k,'') for k in ('application','processid','swapchainaddress'))
        if mango:
            ms, fps = number(item['frametime']), number(item['fps'])
            stamp = number(item.get('elapsed'))
            stamp = stamp/1e9 if stamp is not None else None  # MangoHud uses nanoseconds.
        else:
            ms = number(item.get('msbetweenpresents'))
            if ms is None:
                busy, wait = number(item.get('mscpubusy')), number(item.get('mscpuwait'))
                ms = busy+wait if busy is not None and wait is not None else None
            fps = 1000/ms if ms and ms>0 else None
            stamp = number(item.get('timeinseconds'))
            if stamp is None:
                stamp = number(item.get('cpustarttime'))
                stamp = stamp/1000 if stamp is not None else None
        if ms is None or fps is None or not 0.01 <= ms <= 60000 or not 0 < fps <= 10000:
            rejected += 1
            continue
        group = groups.setdefault(key, [])
        group.append((ms,fps,stamp))
    choices = [{'id':key,'samples':len(v)} for key,v in groups.items()]
    if not groups: raise UserError('Log nie zawiera poprawnych próbek FPS.')
    if len(groups)>1 and stream is None:
        return {'selection_required':True, 'streams':choices}
    selected = stream if stream is not None else next(iter(groups))
    if selected not in groups: raise UserError('Wybierz proces i swapchain z importowanego logu.')
    samples = groups[selected]
    if len(samples)<2: raise UserError('Pomiar wymaga co najmniej dwóch poprawnych próbek.')
    times = [x[0] for x in samples]
    stamps = [x[2] for x in samples if x[2] is not None]
    duration = max(stamps)-min(stamps) if len(stamps)>1 else (sum(times)/1000 if not mango else None)
    # MangoHud log_interval=0 is per-frame. Imported sampled logs are identified
    # by timestamp spacing, and do not pretend to provide per-frame 1% lows.
    deltas = [b-a for a,b in zip(stamps, stamps[1:]) if b>a]
    per_frame = not mango or bool(deltas and statistics.median(deltas)*1000 <= statistics.median(times)*2.5)
    ordered = sorted(times)
    p99 = ordered[min(len(ordered)-1, math.ceil(len(ordered)*.99)-1)]
    avg = 1000/statistics.mean(times) if per_frame else statistics.mean(x[1] for x in samples)
    points = samples[::max(1,math.ceil(len(samples)/240))]
    return {'selection_required':False,'recorder':'mangohud' if mango else 'presentmon','stream':selected,
            'samples':len(samples),'discarded_rows':rejected,'duration_seconds':round(duration,3) if duration is not None else None,
            'average_fps':round(avg,2),'min_fps':round(min(x[1] for x in samples),2),
            'max_fps':round(max(x[1] for x in samples),2),'p99_frametime_ms':round(p99,3),
            'one_percent_low_fps':round(1000/statistics.mean(ordered[-max(1,math.ceil(len(ordered)*.01)):]),2) if per_frame and len(samples)>=100 else None,
            'basis':'per_frame' if per_frame else 'sampled_fps','average_frametime_ms':round(statistics.mean(times),3),
            'series':[{'frame_ms':round(ms,3),'fps':round(fps,2)} for ms,fps,_ in points]}

def settings(data):
    result = {}
    for key,limit in [('resolution',80),('preset',80),('api',80),('upscaling',100),('notes',2000)]:
        value = data.get(key,'')
        if not isinstance(value,str) or len(value)>limit: raise UserError('Niepoprawny opis ustawień pomiaru.')
        result[key] = value.strip()
    return result

class Performance:
    def __init__(self, launcher):
        self.launcher, self.store = launcher, launcher.store
        self.lock = threading.RLock()
        self.active = {}
        # A service restart cannot resume an old capture.
        for session in self.store.list('benchmarks'):
            if session['status'] in {'starting','recording','finishing'}:
                self.store.put('benchmarks',session['id'],{**session,'status':'interrupted','finished_at':time.time()})

    def state(self):
        games = [g for g in self.store.device_candidates() if (g.get('install') or {}).get('ready')]
        return {'sessions':sorted(self.store.list('benchmarks'),key=lambda s:s['started_at'],reverse=True)[:100],
                'games':[{'id':g['id'],'title':g['title'],'version':g['install'].get('version'),
                          'direct':g['install'].get('adapter') not in {'steam','flatpak'}} for g in games],
                'hardware':self.store.get('settings','benchmark_hardware'),
                'mangohud':shutil.which('mangohud'),'presentmon':shutil.which('PresentMon') or shutil.which('PresentMon.exe')}

    def collect_hardware(self):
        return self.store.put('settings','benchmark_hardware',hardware(self.launcher.compatibility.device))

    def _record(self, data, status):
        game = self.launcher.require_game(data.get('game_id',''))
        install = self.store.get('installs',game['id'],{})
        return {'id':uuid.uuid4().hex,'game_id':game['id'],'title':game['title'],
                'profile_id':self.launcher.profiles.active()['id'],'source_id':install.get('source_id',''),
                'port_version':install.get('version','unknown'),'runner':install.get('runner','native'),
                'hardware':self.store.get('settings','benchmark_hardware') or self.collect_hardware(),
                'settings':settings(data),'started_at':time.time(),'status':status,'metrics':None}

    def start(self,data):
        duration, warmup = number(data.get('duration',60)), number(data.get('warmup',5))
        if duration is None or not 1<=duration<=7200 or warmup is None or not 1<=warmup<=600:
            raise UserError('Wybierz czas pomiaru 1–7200 s i rozgrzewkę 1–600 s.')
        with self.lock:
            if self.active: raise UserError('Najpierw zakończ aktywny pomiar.')
            record = self._record(data,'starting')
            install = self.store.get('installs',record['game_id'],{})
            if not install.get('ready') or install.get('adapter') in {'steam','flatpak'}:
                raise UserError('Do automatycznego pomiaru podłącz bezpośredni program gry. Dla klienta Steam / Flatpak zaimportuj log.')
            system = self.launcher.system_key()
            recorder = shutil.which('mangohud') if system=='linux' else data.get('recorder_path') or shutil.which('PresentMon') or shutil.which('PresentMon.exe')
            if system not in {'linux','windows'} or not recorder or not Path(recorder).is_file():
                raise UserError('Zainstaluj MangoHud na Linuxie lub wskaż konsolowy PresentMon na Windowsie. Możesz też zaimportować CSV.')
            root = self.store.root/'benchmarks'/record['id']
            (root/'logs').mkdir(parents=True)
            record.update(duration_requested=duration,warmup_seconds=warmup,recorder='mangohud' if system=='linux' else 'presentmon')
            config = root/'MangoHud.conf'
            if system=='linux':
                config.write_text(f'fps\nframetime\nautostart_log={warmup}\nlog_duration={duration}\nlog_interval=0\noutput_folder={root / "logs"}\npermit_upload=0\n',encoding='utf-8')
            capture = {'record':record,'root':root,'config':config,'recorder':recorder,'stop':threading.Event(),'mono':time.monotonic(),'collector':None}
            self.active[record['id']] = capture
            self.store.put('benchmarks',record['id'],record)
            try:
                launched = self.launcher.launch(record['game_id'],benchmark=capture)
                record.update(status='recording',pid=launched['pid'])
                if system=='windows':
                    log=(root/'recorder.log').open('w')
                    try:
                        capture['collector']=subprocess.Popen([str(recorder),'--process_id',str(launched['pid']),
                            '--output_file',str(root/'logs/presentmon.csv'),'--v1_metrics','--timed',str(duration),
                            '--delay',str(warmup),'--terminate_after_timed','--terminate_on_proc_exit',
                            '--session_name','Recopile_'+record['id'],'--no_console_stats'],stdout=log,stderr=subprocess.STDOUT)
                    finally: log.close()
                self.store.put('benchmarks',record['id'],record)
                threading.Thread(target=self._monitor,args=(capture,),daemon=True,name='recopile-benchmark').start()
                return record
            except Exception as exc:
                self.active.pop(record['id'],None)
                self.store.put('benchmarks',record['id'],{**record,'status':'failed','error':str(exc),'finished_at':time.time()})
                raise

    def wrap(self, command, env, capture):
        if capture['record']['recorder']=='mangohud':
            env = {**env,'MANGOHUD_CONFIGFILE':str(capture['config'])}
            env.pop('MANGOHUD_CONFIG',None)
            command = [capture['recorder'],'--dlsym',*command]
        return command,env

    def _monitor(self,capture):
        record = capture['record']
        capture['stop'].wait(record['warmup_seconds']+record['duration_requested']+1)
        self.finish(record['id'])

    def game_finished(self,ident):
        with self.lock:
            for c in self.active.values():
                if c['record']['game_id']==ident: c['stop'].set()

    def finish(self,ident):
        with self.lock:
            capture = self.active.get(ident)
            if not capture:
                record = self.store.get('benchmarks',ident)
                if not record: raise UserError('Nie znaleziono pomiaru.')
                return record
            record = capture['record']
            if record['status']=='finishing': return self.store.get('benchmarks',ident)
            record.update(status='finishing')
            self.store.put('benchmarks',ident,record)
        # Never stop the game. A stopped MangoHud session is finalized from the
        # raw CSV prefix; its private overlay may finish writing afterwards.
        collector = capture['collector']
        if collector:
            if collector.poll() is None:
                collector.terminate()
                try: collector.wait(timeout=5)
                except subprocess.TimeoutExpired: collector.kill(); collector.wait(timeout=3)
        record.update(elapsed_seconds=round(time.monotonic()-capture['mono'],3),finished_at=time.time())
        try:
            logs = list((capture['root']/'logs').glob('*.csv'))
            parsed = []
            for path in logs:
                if path.name.endswith('_summary.csv') or path.stat().st_size>MAX_LOG: continue
                try:
                    raw=path.read_bytes()
                    result = analyse_csv(raw.decode('utf-8-sig',errors='replace'))
                    if not result.get('selection_required'): parsed.append((result,hashlib.sha256(raw).hexdigest()))
                except UserError: continue
            if len(parsed)!=1:
                raise UserError('Brak jednoznacznego logu FPS. Zaimportuj właściwy CSV lub wybierz proces. Sprawdź dostępność nakładki / uprawnienia PresentMon.')
            metrics,digest = parsed[0]
            record.update(metrics=metrics,log_sha256=digest,status='complete')
        except (OSError,UserError) as exc:
            record.update(status='no_data',error=str(exc))
        with self.lock:
            self.active.pop(ident,None)
            capture['stop'].set()
            return self.store.put('benchmarks',ident,record)

    def import_log(self,data):
        path = Path(str(data.get('path',''))).expanduser()
        if not path.is_file() or path.suffix.lower()!='.csv' or path.stat().st_size>MAX_LOG:
            raise UserError('Wybierz lokalny plik CSV do 32 MB.')
        raw = path.read_bytes()
        if len(raw)>MAX_LOG: raise UserError('Log jest zbyt duży.')
        metrics = analyse_csv(raw.decode('utf-8-sig',errors='replace'),stream=data.get('stream'))
        if metrics.get('selection_required'): return metrics
        device = data.get('hardware')
        if not isinstance(device,dict) or not all(isinstance(device.get(k),str) and device[k].strip() for k in ('system','cpu','gpu')):
            raise UserError('Potwierdź sprzęt, na którym nagrano importowany log.')
        record = self._record(data,'complete')
        record.update(hardware={k:str(device[k])[:200] for k in ('system','cpu','gpu','driver','ram_gb') if device.get(k) is not None},
                      port_version=str(data.get('port_version') or record['port_version'])[:100],
                      metrics=metrics,imported=True,hardware_confirmed=True,finished_at=time.time(),
                      log_sha256=hashlib.sha256(raw).hexdigest())
        return self.store.put('benchmarks',record['id'],record)

    def public_report(self,ident):
        record = self.store.get('benchmarks',ident)
        if not record or record['status']!='complete': raise UserError('Wybierz zakończony pomiar z próbkami FPS.')
        # Deliberate allowlist: no profile, machine ID, PID, paths or raw logs.
        return {k:record[k] for k in ('id','game_id','title','source_id','port_version','runner','hardware','settings','metrics','started_at','log_sha256')}

    def shutdown(self):
        for ident in list(self.active): self.finish(ident)

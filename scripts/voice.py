"""Local voice: Piper process for synthesis, Vosk for recognition, no audio upload."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import wave
import zipfile
from common import CONFIG, ROOT, settings
from speech_text import for_speech

VOICES={'siwis':'Français · féminine (Siwis)', 'tom':'Français · masculine (Tom)'}
MODEL='vosk-model-small-fr-0.22'

def directory():return CONFIG/'voices'

def checked_download(url, target, digest, limit=200*1024*1024):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=target.parent,prefix='.download-')
    try:
        size=0;h=hashlib.sha256()
        with os.fdopen(fd,'wb') as f,urllib.request.urlopen(url,timeout=60) as response:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>limit:raise ValueError('Téléchargement trop volumineux.')
                h.update(chunk);f.write(chunk)
        if h.hexdigest()!=digest:raise ValueError('Empreinte du téléchargement incorrecte. Aucun fichier installé.')
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def install():
    dest=directory();dest.mkdir(parents=True,exist_ok=True)
    assets=json.loads((ROOT/'config/voice-assets.json').read_text())
    for name,asset in assets.items():
        path=dest/name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=asset['sha256']:
            checked_download(asset['url'],path,asset['sha256'])
    if not (dest/MODEL/'am/final.mdl').exists():
        with tempfile.TemporaryDirectory(dir=dest) as stage:
            with zipfile.ZipFile(dest/(MODEL+'.zip')) as z:
                for item in z.infolist():
                    p=Path(item.filename)
                    if p.is_absolute() or '..' in p.parts or p.parts[0]!=MODEL or ((item.external_attr>>16)&0o170000)==0o120000:
                        raise ValueError('Archive vocale invalide.')
                if sum(x.file_size for x in z.infolist())>300*1024*1024:raise ValueError('Archive vocale trop volumineuse.')
                z.extractall(stage)
            import shutil
            if (dest/MODEL).exists():shutil.rmtree(dest/MODEL)
            os.replace(Path(stage)/MODEL,dest/MODEL)
    return {'text':'Les deux voix françaises et la reconnaissance locale sont installées.'}


class Voice:
    def __init__(self):
        self.lock=threading.RLock();self.process=None;self.cancel=threading.Event()
        self.listening=False;self.speaking=False;self.preparing=False;self.transcript='';self.error='';self.worker=None;self.model=None
        self.install_lock=threading.Lock()

    def state(self):
        with self.lock:return {'listening':self.listening,'speaking':self.speaking,'preparing':self.preparing,'transcript':self.transcript,'error':self.error,
            'installed':all((directory()/f'fr_FR-{v}-medium.onnx').exists() for v in VOICES) and (directory()/MODEL/'am/final.mdl').exists()}

    def install(self):
        if not self.install_lock.acquire(False):raise ValueError('Installation vocale déjà en cours.')
        try:return install()
        finally:self.install_lock.release()

    def stop(self):
        with self.lock:
            self.cancel.set()
            if self.process and self.process.poll() is None:self.process.terminate()
        if self.worker and self.worker is not threading.current_thread():self.worker.join(timeout=3)
        return {'text':'Arrêt demandé.'}

    def speak(self, data):
        text=for_speech(data.get('text',''))[:12000]
        selected=data.get('voice') or settings().get('voice_model','siwis')
        if selected not in VOICES:raise ValueError('Voix inconnue.')
        if not text:raise ValueError('Aucun texte à lire.')
        model=directory()/f'fr_FR-{selected}-medium.onnx'
        if not model.exists():raise ValueError('Installe les voix locales dans Configuration > Voix.')
        self.stop()
        if self.worker and self.worker.is_alive():raise ValueError('Le moteur termine la demande précédente. Réessaie.')
        self.cancel=threading.Event();self.error='';self.preparing=True
        def work():
            try:
                with tempfile.TemporaryDirectory(prefix='jarvis-voice-') as tmp:
                    wav=Path(tmp)/'speech.wav'
                    with self.lock:
                        if self.cancel.is_set():return
                        self.process=subprocess.Popen([sys.executable,'-m','piper','--model',str(model),'--output_file',str(wav)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    self.process.communicate(text.encode(),timeout=180)
                    if self.cancel.is_set():return
                    if self.process.returncode or not wav.exists():raise ValueError('Synthèse vocale indisponible. Réinstalle les composants vocaux.')
                    with self.lock:
                        if self.cancel.is_set():return
                        self.preparing=False;self.speaking=True
                        self.process=subprocess.Popen(['/usr/bin/afplay',str(wav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    code=self.process.wait(timeout=900)
                    if code and not self.cancel.is_set():raise ValueError('La sortie audio macOS est indisponible.')
            except Exception:
                if not self.cancel.is_set():self.error='Lecture vocale impossible. Vérifie la sortie audio et les composants vocaux.'
            finally:
                with self.lock:
                    if self.process and self.process.poll() is None:self.process.kill()
                    self.preparing=False;self.speaking=False;self.process=None
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
        return {'text':'Préparation de la voix locale.'}

    def listen(self):
        if not (directory()/MODEL/'am/final.mdl').exists():raise ValueError('Installe les composants vocaux dans Configuration > Voix.')
        self.stop()
        if self.worker and self.worker.is_alive():raise ValueError('Le moteur termine la demande précédente. Réessaie.')
        self.cancel=threading.Event();self.transcript='';self.error='';self.listening=True
        def work():
            try:
                import sounddevice as sd
                import vosk
                vosk.SetLogLevel(-1)
                if self.model is None:self.model=vosk.Model(str(directory()/MODEL))
                info=sd.query_devices(kind='input');rate=int(info['default_samplerate'])
                recognizer=vosk.KaldiRecognizer(self.model,rate);chunks=queue.Queue(maxsize=32);parts=[]
                def callback(indata,frames,timing,status):
                    try:chunks.put_nowait(bytes(indata))
                    except queue.Full:pass
                with sd.RawInputStream(samplerate=rate,blocksize=4000,dtype='int16',channels=1,callback=callback):
                    deadline=time.monotonic()+120
                    while not self.cancel.is_set() and time.monotonic()<deadline:
                        try:chunk=chunks.get(timeout=.15)
                        except queue.Empty:continue
                        if recognizer.AcceptWaveform(chunk):parts.append(json.loads(recognizer.Result()).get('text',''))
                        partial=json.loads(recognizer.PartialResult()).get('partial','')
                        self.transcript=' '.join(parts+[partial]).strip()
                    parts.append(json.loads(recognizer.FinalResult()).get('text',''));self.transcript=' '.join(parts).strip()
            except Exception:self.error='Microphone indisponible. Autorise Jarvis (ou Python) dans Réglages Système > Confidentialité > Microphone et vérifie le périphérique d’entrée.'
            finally:self.listening=False
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
        return {'text':'Écoute locale, deux minutes maximum. Clique sur Terminer pour relire la transcription.'}

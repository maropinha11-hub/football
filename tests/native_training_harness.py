"""Real SDL/X11 input and telemetry from the rendered training executable."""
import json
import os
from pathlib import Path
import subprocess
import time

KEY_BITS={key:1<<i for i,key in enumerate([
    'w','s','a','d','j','i','l','k','Shift_L','space','q',
    'Left','Right','Up','Down','r','1','2','3','4','5','Tab','6','t','F4','F5','F6'])}

class NativeTraining:
    def __init__(self,build,output,display=':94',analog_pad=False,camera=2,config_overrides=None):
        self.build=Path(build).resolve();self.output=Path(output).resolve()
        self.output.mkdir(parents=True,exist_ok=False)
        self.log=self.output/'game.log';self.cache=[];self.offset=0;self.pending=b''
        self.held=set();self.server=None;self.game=None;self.window=None
        self.env=os.environ.copy()
        runtime=self.output/'xdg-runtime';runtime.mkdir(mode=0o700)
        self.env.update(DISPLAY=display,SDL_VIDEODRIVER='x11',ALSOFT_DRIVERS='null',
                        LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS=os.environ.get('FOOTBALL_TEST_GL_THREADS','2'),
                        XDG_RUNTIME_DIR=str(runtime),XDG_CACHE_HOME=str(self.output/'cache'))
        self.camera=camera
        self.config_overrides=config_overrides or {}
        self.pad_file=None;self.pad_values=[0,0,0,0,-32768,-32768,0]
        if analog_pad:
            root=Path(__file__).resolve().parents[1]
            native=Path(os.environ.get('FOOTBALL_NATIVE_ROOT','/workspace/.football-native'))/'root/usr'
            library=self.output/'virtual-pad.so'
            subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',
                            '-I'+str(native/'include'),'-I'+str(native/'include/x86_64-linux-gnu'),
                            str(root/'tests/virtual_training_pad.cpp'),
                            '-L'+str(native/'lib/x86_64-linux-gnu'),'-lSDL2','-ldl','-o',str(library)],check=True)
            self.pad_file=self.output/'pad.txt'
            self.pad(0,0)
            self.env.update(LD_PRELOAD=str(library),FOOTBALL_TEST_PAD_FILE=str(self.pad_file))
    def pad(self,x,y,sprint=False,close=False,buttons=0):
        self.pad_values=[int(x*32767),int(y*32767),0,0,-32768,32767 if close else-32768,
                         buttons|((1<<10)if sprint else 0)] # SDL right shoulder = RB.
        temporary=self.pad_file.with_suffix('.new');temporary.write_text(' '.join(map(str,self.pad_values)))
        temporary.replace(self.pad_file)
    def frames(self):
        if not self.log.exists():return self.cache
        with self.log.open('rb')as stream:
            stream.seek(self.offset);fresh=stream.read();self.offset=stream.tell()
        lines=(self.pending+fresh).split(b'\n');self.pending=lines.pop()
        for line in lines:
            if line.startswith(b'TRAINING_FRAME '):self.cache.append(json.loads(line[15:]))
        return self.cache
    def wait(self,predicate,seconds=30):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if self.game and self.game.poll()is not None:raise RuntimeError('game exited '+str(self.game.returncode))
            result=predicate()
            if result:return result
            time.sleep(.03)
        raise TimeoutError('SDL/telemetry acknowledgement; inspect '+str(self.log))
    def advance(self,milliseconds):
        start=self.frames()[-1]['t']
        self.wait(lambda:self.frames()[-1]['t']>=start+milliseconds)
        return [f for f in self.frames()if f['t']>start]
    def keys(self,names,down):
        names=list(names)
        if not names:return
        def send():
            subprocess.run(['xdotool','keydown'if down else'keyup','--window',self.window,*names],
                           env=self.env,check=True)
        send()
        if down:self.held.update(names)
        else:self.held.difference_update(names)
        mask=sum(KEY_BITS[n]for n in names if n in KEY_BITS);sent=time.monotonic()
        if mask:
            def acknowledged():
                nonlocal sent
                if self.frames()[-1]['keys']&mask==(mask if down else 0):return True
                if not down and time.monotonic()-sent>1:send();sent=time.monotonic()
                return False
            self.wait(acknowledged)
    def reset(self):
        if self.pad_file:self.pad(0,0)
        self.keys(self.held,False)
        old=self.log.read_text().count('TRAINING_RESET')
        self.keys(['1'],True);self.keys(['1'],False)
        self.wait(lambda:self.log.read_text().count('TRAINING_RESET')>old)
        self.advance(600)
    def __enter__(self):
        root=Path(__file__).resolve().parents[1];config=self.output/'test.config'
        config.write_text((root/'config/training.config').read_text()+
                          '\n"context_x" "960"\n"context_y" "540"\n"training_camera" "'+str(self.camera)+'"\n'+
                          '"pes3_preview" "false"\n'+
                          ''.join('"'+key+'" "'+str(value)+'"\n' for key,value in self.config_overrides.items()))
        socket=Path('/tmp/.X11-unix')/('X'+self.env['DISPLAY'].lstrip(':'))
        if socket.exists():raise RuntimeError('test display already in use')
        try:
            with (self.output/'xvfb.log').open('w')as stream:
                self.server=subprocess.Popen(['Xvfb',self.env['DISPLAY'],'-screen','0','960x540x24','-nolisten','tcp'],
                                             env=self.env,stdout=stream,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+10
            while subprocess.run(['xdpyinfo'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
                if self.server.poll()is not None or time.monotonic()>deadline:raise RuntimeError('Xvfb not ready')
                time.sleep(.05)
            with self.log.open('w')as stream:
                self.game=subprocess.Popen([str(self.build/'gameplayfootball'),'--config',str(config),'--training','--telemetry'],
                                           cwd=self.build,env=self.env,stdout=stream,stderr=subprocess.STDOUT)
            self.wait(lambda:self.frames()and self.frames()[-1]['t']>=500,seconds=60)
            windows=self.wait(lambda:subprocess.run(['xdotool','search','--pid',str(self.game.pid)],env=self.env,
                                 text=True,capture_output=True).stdout.splitlines())
            self.window=windows[-1]
            subprocess.run(['xdotool','windowfocus',self.window],env=self.env,check=True)
            if self.pad_file:self.wait(lambda:self.frames()[-1]['controller']>0)
            return self
        except BaseException:
            self.__exit__(None,None,None);raise
    def __exit__(self,*_):
        if self.game and self.game.poll()is None:self.game.terminate()
        if self.server and self.server.poll()is None:self.server.terminate()
        for process in (self.game,self.server):
            if process:
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

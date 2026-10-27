"""Local native-physics protocol, usable without PyTorch."""
import os
import struct
import subprocess
import numpy as np

class Environment:
    def __init__(self, executable, count, seed):
        if not 1<=count<=256:raise ValueError('invalid environment count')
        self.process=subprocess.Popen([str(executable),str(count),str(seed),os.environ.get('FOOTBALL_RL_REFERENCE','legacy')],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        try:
            magic,self.features,self.actions,self.count=struct.unpack('<4I',self.read(16))
            if magic not in(0x46504232,0x46504233):raise ValueError('unknown physics protocol')
            self.diagnostics=6 if magic==0x46504232 else struct.unpack('<I',self.read(4))[0]
            if self.features!=148 or self.actions!=20 or self.count!=count or self.diagnostics not in(6,9):raise ValueError('incompatible physics dimensions')
            self.observation,*_=self.receive()
        except BaseException:
            self.process.terminate();self.process.wait(timeout=10);raise
    def read(self, size):
        data=self.process.stdout.read(size)
        if len(data)!=size:raise RuntimeError(f'physics server ended ({self.process.poll()}); expected {size}, received {len(data)} bytes')
        return data
    def receive(self):
        n=self.count;f=self.features
        a=np.frombuffer(self.read((n*f+n+n+n*self.diagnostics)*4),dtype='<f4').copy()
        if not np.isfinite(a).all():raise ValueError('non-finite native physics result')
        return a[:n*f].reshape(n,f),a[n*f:n*f+n],a[n*f+n:n*f+2*n],a[n*f+2*n:].reshape(n,self.diagnostics)
    def reset(self, level):
        if not np.isfinite(level)or not 0<=level<=1.5:raise ValueError('invalid curriculum level')
        self.process.stdin.write(struct.pack('<If',1,level));self.process.stdin.flush()
        self.observation,*_=self.receive();return self.observation
    def step(self, action, level):
        action=np.asarray(action,dtype='<f4')
        if action.shape!=(self.count,self.actions)or not np.isfinite(action).all():raise ValueError('invalid action tensor')
        if not np.isfinite(level)or not 0<=level<=1.5:raise ValueError('invalid curriculum level')
        self.process.stdin.write(struct.pack('<If',0,level)+action.tobytes());self.process.stdin.flush()
        result=self.receive();self.observation=result[0];return result
    def close(self):
        if self.process.poll()is None:
            try:self.process.stdin.write(struct.pack('<I',2));self.process.stdin.flush()
            except BrokenPipeError:pass
            self.process.wait(timeout=10)
        self.process.stdin.close();self.process.stdout.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

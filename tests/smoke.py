#!/usr/bin/env python3
"""Exercise the actual daemon without a robot. Avahi/Bonjour must be running."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time


def main():
    binary, probe = map(lambda x: str(Path(x).resolve()), sys.argv[1:])
    result = subprocess.run([binary, '--help'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and 'allow-remote-connections' in result.stdout, result
    for port in [8596, 8597]:
        with socket.socket() as connection:
            assert connection.connect_ex(('127.0.0.1', port)) != 0, f'Port {port} already in use; stop the existing TDM before testing'
    with tempfile.TemporaryFile(mode='w+b') as log:
        options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
        daemon = subprocess.Popen([binary], stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if daemon.poll() is not None:
                    raise RuntimeError('Daemon exited before accepting connections')
                with socket.socket() as connection:
                    if connection.connect_ex(('127.0.0.1', 8597)) == 0:
                        break
                time.sleep(0.1)
            else:
                raise RuntimeError('Daemon did not start within 15 seconds')
            for transport in ['tcp', 'websocket']:
                subprocess.run([probe, transport], check=True, timeout=10)
            second = subprocess.run([binary], capture_output=True, text=True, timeout=10)
            assert second.returncode != 0 and 'already running' in second.stdout + second.stderr, second
            daemon.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
            status = daemon.wait(timeout=10)
            assert status == 0 or (os.name == 'nt' and status in [0xC000013A, -1073741510]), status
        except Exception:
            status = daemon.poll()
            if status is None:
                print('Daemon was still running when the smoke test failed', file=sys.stderr)
            elif os.name != 'nt' and status < 0:
                print(f'Daemon terminated by {signal.Signals(-status).name} ({status})', file=sys.stderr)
            else:
                print(f'Daemon exited with status {status}', file=sys.stderr)
            log.seek(0)
            print(log.read().decode(errors='replace'), file=sys.stderr)
            raise
        finally:
            if daemon.poll() is None:
                daemon.kill()
                daemon.wait()


if __name__ == '__main__':
    main()

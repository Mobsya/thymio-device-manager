#!/usr/bin/env python3
"""Check a staged package's architecture, shared libraries and relocated startup."""
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile


def pe_info(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise RuntimeError('Invalid PE file: ' + str(path))
    machine, sections = struct.unpack_from('<HH', data, pe + 4)
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    directory = optional + (112 if magic == 0x20b else 96)
    table = optional + optional_size

    def offset(rva):
        for index in range(sections):
            section = table + 40 * index
            size, address, raw_size, raw = struct.unpack_from('<IIII', data, section + 8)
            if address <= rva < address + max(size, raw_size):
                return raw + rva - address
        raise RuntimeError('Unmapped PE address in ' + str(path))

    imports = []
    rva = struct.unpack_from('<I', data, directory + 8)[0]
    if rva:
        cursor = offset(rva)
        while any(data[cursor:cursor + 20]):
            name = offset(struct.unpack_from('<I', data, cursor + 12)[0])
            imports.append(data[name:data.index(b'\0', name)].decode('ascii').lower())
            cursor += 20
    return machine, imports


def check(stage):
    windows = platform.system() == 'Windows'
    binary = stage / 'bin' / ('thymio-device-manager.exe' if windows else 'thymio-device-manager')
    if not binary.is_file():
        raise RuntimeError('Missing executable: ' + str(binary))
    if platform.system() == 'Darwin':
        output = subprocess.check_output(['otool', '-L', binary], text=True)
        for line in output.splitlines():
            if line.startswith('\t'):
                name = line.strip().split(' (', 1)[0]
                if not name.startswith(('/usr/lib/', '/System/Library/')):
                    raise RuntimeError('Non-system macOS dependency: ' + name)
        subprocess.run(['codesign', '--verify', '--strict', binary], check=True)
        load_commands = subprocess.check_output(['otool', '-l', binary], text=True)
        for minimum in re.findall(r'\bminos (\d+\.\d+)', load_commands):
            if tuple(map(int, minimum.split('.'))) > (11, 0):
                raise RuntimeError('Binary exceeds macOS 11 baseline: ' + minimum)
    elif windows:
        system = Path(os.environ['SystemRoot']) / 'System32'
        for image in [binary, *binary.parent.glob('*.dll')]:
            machine, imports = pe_info(image)
            if machine != 0x8664:
                raise RuntimeError('Expected x64 PE: ' + str(image))
            for name in imports:
                if re.match(r'(vcruntime\d|msvcp\d|msvcr\d)', name):
                    raise RuntimeError('Expected a static MSVC runtime, found: ' + name)
                if not name.startswith(('api-ms-', 'ext-ms-')) and not (system / name).exists() and not (binary.parent / name).exists():
                    raise RuntimeError(str(image) + ' has an unbundled dependency: ' + name)
    else:
        output = subprocess.check_output(['ldd', binary], text=True)
        if 'not found' in output or re.search(r'lib(boost|ssl|crypto|usb)', output):
            raise RuntimeError('Unbundled application dependency:\n' + output)
        for path in re.findall(r'=> (/\S+)', output):
            if not path.startswith(('/lib/', '/lib64/', '/usr/lib/', '/usr/lib64/')):
                raise RuntimeError('Non-system library path: ' + path)
        versions = subprocess.check_output(['readelf', '--version-info', binary], text=True)
        for version in re.findall(r'\bGLIBC_(\d+)\.(\d+)\b', versions):
            if tuple(map(int, version)) > (2, 35):
                raise RuntimeError('Binary exceeds the Ubuntu 22.04 glibc baseline')
    # Relocate the complete archive contents, with library search overrides removed.
    with tempfile.TemporaryDirectory(prefix='tdm-package-check-') as temp:
        relocated = Path(temp) / 'package'
        shutil.copytree(stage, relocated)
        env = {k: v for k, v in os.environ.items() if k not in ['LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH']}
        result = subprocess.run([str(relocated / 'bin' / binary.name), '--help'], cwd=temp,
                                env=env, capture_output=True, text=True, timeout=15)
        if result.returncode != 1 or 'allow-remote-connections' not in result.stdout:
            raise RuntimeError('Relocated executable failed: ' + result.stdout + result.stderr)
    print('Verified package:', stage)


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())

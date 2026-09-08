#!/usr/bin/env python3
"""Build TDM. Actions: deps, configure, build, test, package, universal, source, clean.

Requires CMake >= 3.25, Ninja, a C++17 compiler, curl, Perl, and GNU Make.
Windows additionally requires the VS 2022 x64 developer environment and NASM.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / 'dependencies.lock.json'
LOCK = json.loads(LOCK_PATH.read_text())
DOWNLOADS = ROOT / '.cache/downloads'
PRESETS = ['linux-x64', 'windows-x64', 'macos-x86_64', 'macos-arm64']


def run(command, **kwargs):
    command = [str(x) for x in command]
    print('+', subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for name, spec in LOCK['dependencies'].items():
        dest = DOWNLOADS / spec['file']
        if dest.exists() and sha256(dest) == spec['sha256']:
            continue
        partial = dest.with_suffix(dest.suffix + '.part')
        try:
            run(['curl', '--fail', '--location', '--retry', '3', '--output', partial, spec['url']])
            if sha256(partial) != spec['sha256']:
                raise RuntimeError('Checksum mismatch: ' + name)
            partial.replace(dest)
        finally:
            partial.unlink(missing_ok=True)


def resolve_preset(preset):
    if preset == 'native':
        system = platform.system()
        machine = platform.machine().lower()
        if system == 'Darwin':
            preset = 'macos-' + ('arm64' if machine in ['arm64', 'aarch64'] else 'x86_64')
        elif system == 'Windows' and machine in ['amd64', 'x86_64']:
            preset = 'windows-x64'
        elif system == 'Linux' and machine in ['amd64', 'x86_64']:
            preset = 'linux-x64'
        else:
            raise RuntimeError('Unsupported host architecture: ' + system + ' ' + machine)
    if preset not in PRESETS:
        raise RuntimeError('Unknown preset: ' + preset)
    expected = 'Darwin' if preset.startswith('macos-') else ('Windows' if preset.startswith('windows-') else 'Linux')
    if platform.system() != expected:
        raise RuntimeError(preset + ' requires a ' + expected + ' host')
    return preset


def deps(preset, jobs):
    fetch()
    if not shutil.which('ninja'):
        raise RuntimeError('Ninja is required. See README.md for tool installation instructions.')
    arch = 'arm64' if preset == 'macos-arm64' else 'x86_64'
    prefix = ROOT / 'build/deps' / preset
    build_dir = ROOT / 'build/bootstrap' / preset
    # ExternalProject stamps do not notice edits to a Python recipe. Invalidate
    # installed libraries and source build trees when any dependency input changes.
    inputs = hashlib.sha256()
    for path in [LOCK_PATH, ROOT / 'scripts/build_dependency.py', ROOT / 'cmake/bootstrap/CMakeLists.txt', ROOT / 'cmake/FetchLocked.cmake']:
        inputs.update(path.read_bytes())
    inputs.update(str(prefix).encode())
    stamp = build_dir / 'tdm-inputs.sha256'
    fingerprint = inputs.hexdigest()
    if stamp.exists() and stamp.read_text() != fingerprint:
        shutil.rmtree(build_dir)
        shutil.rmtree(prefix, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    stamp.write_text(fingerprint)
    run(['cmake', '-S', ROOT / 'cmake/bootstrap', '-B', build_dir, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DTDM_DOWNLOAD_DIR=' + str(DOWNLOADS),
         '-DTDM_DEPS_PREFIX=' + str(prefix), '-DTDM_ARCH=' + arch,
         '-DTDM_MACOS_MIN=11.0'])
    # Each dependency may use JOBS itself: don't multiply memory use by running all three at once.
    env = os.environ.copy()
    env['CMAKE_BUILD_PARALLEL_LEVEL'] = str(jobs)
    run(['cmake', '--build', build_dir, '--parallel', '1'], env=env)


def configure(preset, jobs):
    deps(preset, jobs)
    run(['cmake', '--preset', preset], cwd=ROOT)


def build(preset, jobs):
    configure(preset, jobs)
    run(['cmake', '--build', '--preset', preset, '--parallel', str(jobs)], cwd=ROOT)


def test(preset, jobs):
    build(preset, jobs)
    run(['ctest', '--preset', preset, '--output-on-failure'], cwd=ROOT)


def collect_licenses(destination):
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'license.txt', destination / 'aseba-LGPL-3.0.txt')
    shutil.copy2(ROOT / 'authors.txt', destination / 'aseba-authors.txt')
    for name, spec in LOCK['dependencies'].items():
        archive = DOWNLOADS / spec['file']
        if spec['kind'] == 'archive':
            with tarfile.open(archive) as source:
                for member in source.getmembers():
                    parts = Path(member.name).parts
                    if len(parts) == 2 and parts[-1].lower() in ['license', 'license.txt', 'license.md', 'license.rst', 'license_1_0.txt', 'copying', 'license.md.in'] and member.isfile():
                        stream = source.extractfile(member)
                        (destination / (name + '-' + parts[-1])).write_bytes(stream.read())
        elif name in ['belle', 'bonjour_header', 'catch2_license']:
            shutil.copy2(archive, destination / (name + '.txt'))


def checksums():
    artifacts = sorted(p for p in (ROOT / 'dist').iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (ROOT / 'dist/SHA256SUMS').write_text(''.join(sha256(p) + '  ' + p.name + '\n' for p in artifacts))


def stage(preset):
    stage_dir = ROOT / 'build/stage' / preset
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    run(['cmake', '--install', ROOT / 'build' / preset, '--prefix', stage_dir, '--config', 'Release'])
    if preset == 'windows-x64':
        # dnssd64.lib imports dnssd.dll. The file named dnssd.dll in the old x64 folder is x86!
        dll = DOWNLOADS / LOCK['dependencies']['bonjour_dll']['file']
        shutil.copy2(dll, stage_dir / 'bin/dnssd.dll')
    add_package_metadata(stage_dir)
    return stage_dir


def add_package_metadata(stage_dir):
    for name in ['README.md', 'VERSION.txt', 'dependencies.lock.json', 'PROVENANCE.md']:
        shutil.copy2(ROOT / name, stage_dir / name)
    shutil.copytree(ROOT / 'docs', stage_dir / 'docs', dirs_exist_ok=True)
    if platform.system() == 'Linux':
        shutil.copytree(ROOT / 'packaging/linux', stage_dir / 'share/thymio-device-manager', dirs_exist_ok=True)
    collect_licenses(stage_dir / 'licenses')


def archive_stage(stage_dir, platform_name):
    version = (ROOT / 'VERSION.txt').read_text().strip()
    stem = 'thymio-device-manager-' + version + '-' + platform_name
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    if platform_name.startswith('windows'):
        archive = dist / (stem + '.zip')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
            for path in sorted(stage_dir.rglob('*')):
                if path.is_file():
                    output.write(path, Path(stem) / path.relative_to(stage_dir))
    else:
        archive = dist / (stem + '.tar.gz')
        with tarfile.open(archive, 'w:gz') as output:
            output.add(stage_dir, arcname=stem)
    checksums()
    print('Created', archive)


def package(preset, jobs):
    build(preset, jobs)
    stage_dir = stage(preset)
    executable = stage_dir / 'bin' / ('thymio-device-manager.exe' if preset == 'windows-x64' else 'thymio-device-manager')
    if preset.startswith('macos'):
        run(['codesign', '--force', '--sign', '-', executable])
    run([sys.executable, ROOT / 'scripts/check_artifact.py', stage_dir])
    archive_stage(stage_dir, preset)


def universal(jobs):
    if platform.system() != 'Darwin':
        raise RuntimeError('Universal packaging requires macOS')
    for preset in ['macos-x86_64', 'macos-arm64']:
        build(preset, jobs)
        stage(preset)
    merge_universal(ROOT / 'build/stage/macos-x86_64', ROOT / 'build/stage/macos-arm64')


def merge_universal(intel, arm):
    result = ROOT / 'build/stage/macos-universal'
    if result.exists():
        shutil.rmtree(result)
    shutil.copytree(intel, result)
    binary = 'bin/thymio-device-manager'
    run(['lipo', '-create', intel / binary, arm / binary, '-output', result / binary])
    run(['lipo', result / binary, '-verify_arch', 'arm64', 'x86_64'])
    run(['codesign', '--force', '--sign', '-', result / binary])
    run([sys.executable, ROOT / 'scripts/check_artifact.py', result])
    archive_stage(result, 'macos-universal')


def source_bundle():
    fetch()
    version = (ROOT / 'VERSION.txt').read_text().strip()
    stem = 'thymio-device-manager-' + version + '-source'
    (ROOT / 'dist').mkdir(exist_ok=True)
    with tarfile.open(ROOT / 'dist' / (stem + '.tar.gz'), 'w:gz') as output:
        def source_filter(member):
            if '__pycache__' in Path(member.name).parts or member.name.endswith(('.pyc', '/.DS_Store')):
                return None
            return member
        for path in sorted(ROOT.iterdir()):
            if path.name not in ['build', 'dist', '.cache', '.git', '__pycache__', '.DS_Store']:
                output.add(path, arcname=stem + '/' + path.name, filter=source_filter)
        # Include every exact dependency input for rebuilding without library downloads.
        for spec in LOCK['dependencies'].values():
            output.add(DOWNLOADS / spec['file'], arcname=stem + '/.cache/downloads/' + spec['file'])
    checksums()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['deps', 'configure', 'build', 'test', 'package', 'universal', 'source', 'clean', 'merge-universal'])
    parser.add_argument('--preset', default='native')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--intel', type=Path)
    parser.add_argument('--arm', type=Path)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.action == 'clean':
        shutil.rmtree(ROOT / 'build', ignore_errors=True)
    elif args.action == 'source':
        source_bundle()
    elif args.action == 'universal':
        universal(args.jobs)
    elif args.action == 'merge-universal':
        if platform.system() != 'Darwin' or not args.intel or not args.arm:
            parser.error('merge-universal requires macOS, --intel and --arm staging folders')
        merge_universal(args.intel.resolve(), args.arm.resolve())
    else:
        globals()[args.action](resolve_preset(args.preset), args.jobs)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))

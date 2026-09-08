#!/usr/bin/env python3
"""Native static dependency recipes, called by CMake ExternalProject."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(command, source, env):
    print('+', subprocess.list2cmdline([str(x) for x in command]), flush=True)
    log = source / 'tdm-build.log'
    with log.open('a') as output:
        result = subprocess.run(command, cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-80:]), file=sys.stderr)
        print('Full dependency build log:', log, file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dependency', choices=['boost', 'openssl'])
    for arg in ['source', 'prefix', 'arch', 'deployment-target']:
        parser.add_argument('--' + arg, required=True)
    parser.add_argument('--jobs', default=os.environ.get('CMAKE_BUILD_PARALLEL_LEVEL', '2'))
    args = parser.parse_args()
    source = Path(args.source).resolve()
    prefix = Path(args.prefix).resolve()
    env = os.environ.copy()
    windows = sys.platform == 'win32'
    mac = sys.platform == 'darwin'
    if mac:
        env['MACOSX_DEPLOYMENT_TARGET'] = args.deployment_target
    if args.dependency == 'boost':
        # Preserve timestamps so b2 can skip spawning a separate copy process for
        # each of Boost's ~16,000 headers (especially costly on Windows).
        shutil.copytree(source / 'boost', prefix / 'include/boost', dirs_exist_ok=True)
        if windows:
            run(['cmd', '/c', 'bootstrap.bat', 'msvc'], source, env)
            command = [str(source / 'b2.exe'), 'toolset=msvc', 'runtime-link=static']
        else:
            run(['sh', './bootstrap.sh'], source, env)
            command = [str(source / 'b2')]
        command += ['install', '--prefix=' + str(prefix), '--layout=system', '--disable-icu', '-j' + args.jobs,
                    'link=static', 'variant=release', 'threading=multi', 'address-model=64', 'cxxstd=17']
        if mac:
            flags = f'-arch {args.arch} -mmacosx-version-min={args.deployment_target}'
            command += ['toolset=clang', 'architecture=' + ('arm' if args.arch == 'arm64' else 'x86'),
                        'cxxflags=' + flags + ' -fPIC -Wno-enum-constexpr-conversion -D_LIBCPP_ENABLE_CXX17_REMOVED_UNARY_BINARY_FUNCTION',
                        'cflags=' + flags + ' -fPIC', 'linkflags=' + flags]
        elif not windows:
            command += ['cxxflags=-fPIC', 'cflags=-fPIC']
        command += ['--with-' + component for component in
                    ['atomic', 'chrono', 'date_time', 'filesystem', 'program_options', 'regex', 'thread']]
        run(command, source, env)
    else:
        target = 'VC-WIN64A' if windows else ('darwin64-' + args.arch + '-cc' if mac else 'linux-x86_64')
        command = ['perl', str(source / 'Configure'), target, 'no-shared', 'no-module', 'no-tests',
                   '--prefix=' + str(prefix), '--libdir=lib']
        if windows:
            command += ['-static']
        elif mac:
            command += ['-mmacosx-version-min=' + args.deployment_target]
        else:
            command += ['-fPIC']
        run(command, source, env)
        make = ['nmake'] if windows else ['make', '-j' + args.jobs]
        run(make, source, env)
        run(make + ['install_sw'], source, env)


if __name__ == '__main__':
    main()

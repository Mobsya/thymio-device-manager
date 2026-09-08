# Thymio Device Manager

Standalone bridge between Thymio robots and applications using the TDM TCP and
WebSocket protocol. This project includes the Aseba compiler and protocol support
it needs; Qt, Thymio Suite, the simulator, and the separate firmware recovery CLI
are not required or built. Firmware updating through the TDM remains available.

## Run a release archive

Extract the archive and run `bin/thymio-device-manager` (Windows:
`bin\thymio-device-manager.exe`). Keep bundled DLLs beside the Windows executable.
Only one device manager can run at a time, including one started by Thymio Suite.
Stop it with Ctrl+C. `--help` shows the existing options and exits with status 1.

The TCP endpoint uses port 8596 and the WebSocket endpoint uses port 8597. Remote
connections remain disabled by default; `--allow-remote-connections` enables the
existing remote-access behavior. There is no GUI or automatically installed service.

Supported release targets:

| Archive | Minimum environment | Runtime prerequisites |
| --- | --- | --- |
| Linux x64 | Ubuntu 22.04 or compatible newer Linux | Avahi client libraries, D-Bus and running Avahi daemon; USB permissions |
| macOS universal | macOS 11+, Intel or Apple Silicon | System Bonjour and IOKit |
| Windows x64 | Windows 10/11 | Bonjour service, applicable Thymio USB drivers |

On Ubuntu, install `avahi-daemon libavahi-client3` and ensure `avahi-daemon` is
running. Copy `share/thymio-device-manager/70-thymio.rules` from a release archive
to `/etc/udev/rules.d/`, then run `sudo udevadm control --reload-rules` and reconnect
the robot. The rule grants access to the active desktop user. A headless account
needs a distribution-appropriate group-based USB permission rule instead.

On Windows, installing the x64 Bonjour service is separate from extracting the
archive: the included `dnssd.dll` is its client library, not the service. Existing
Bonjour installations can be used. The pinned legacy service installer is fetched
into `.cache/downloads/bonjour_msi-Bonjour64.msi` by `make deps` for developer/CI
setup; it is not silently installed or bundled in the binary archive. If a robot
is not detected, install its Thymio USB driver through the device's normal driver
setup. See [runtime notes](docs/runtime.md).

These releases have no trusted publisher signature or Apple notarization. macOS
binaries use ad-hoc signatures; downloaded archives may require explicit approval
in macOS Privacy & Security before execution.

## Build locally

Requirements: Python 3.9+, CMake 3.25+, Ninja, curl, Perl, GNU Make, and a C++17
compiler. Sources are fetched at exact revisions with SHA-256 verification.
The first build downloads approximately 270 MB and needs several GB of disk space.
No installed Boost, OpenSSL, Aseba checkout, or Git submodules are needed.

Ubuntu 22.04:

```sh
sudo apt-get update
sudo apt-get install build-essential python3 python3-pip ninja-build curl perl pkg-config libavahi-client-dev avahi-daemon
python3 -m pip install --user 'cmake>=3.25'
export PATH="$HOME/.local/bin:$PATH"
make test JOBS=4
make package JOBS=4
```

macOS (install Xcode Command Line Tools first):

```sh
brew install cmake ninja python make
make test JOBS=4
make package JOBS=4
make universal JOBS=4
```

`make universal` builds Intel and ARM dependencies separately, uses a native host
`flatc` for schema generation, combines the binaries, and signs the final result.
It executes the package startup check on the host architecture. CI tests each
architecture natively and tests the combined executable on both.

Windows: install Visual Studio 2022 Build Tools with Desktop development with C++,
Python, CMake, Ninja, GNU Make, Perl and NASM. Put them on PATH and run in an **x64
Native Tools Command Prompt for VS 2022**:

```bat
make deps PYTHON=python JOBS=4
make test PYTHON=python JOBS=4
make package PYTHON=python JOBS=4
```

Install/start Bonjour before `make test`. GNU Make is only the command interface;
the compiler is MSVC, not MinGW. Python can also invoke every action directly:
`python scripts/build.py build --preset windows-x64 --jobs 4`.

| Command | Result |
| --- | --- |
| `make deps` | Verified downloads and static Boost/OpenSSL plus host `flatc` |
| `make configure` | Dependencies and application CMake configuration |
| `make build` | Executable and tests |
| `make test` | Build, unit tests and daemon smoke test |
| `make package` | Native archive, runtime dependency checks and checksums |
| `make universal` | Universal macOS archive |
| `make source` | Source archive including all pinned dependency downloads |
| `make clean` | Remove `build/`; preserve download cache and release archives |

`PRESET` defaults to the host. Explicit values: `linux-x64`, `windows-x64`,
`macos-x86_64`, `macos-arm64`. `JOBS` defaults to 2 to limit compiler memory use.
After `make deps`, the standard `cmake --preset <preset>`, `cmake --build --preset
<preset>` and `ctest --preset <preset>` commands work too.

Build products go to `build/<preset>/bin`, packages to `dist/`. The source bundle
includes `.cache/downloads`, allowing rebuilds without library downloads once the
documented system tools and platform prerequisites are installed. To update a
dependency, update its revision/URL and verified SHA-256 in `dependencies.lock.json`,
run `make clean`, and validate all platforms. Do not replace Mobsya forks with
unmodified upstream releases without testing their local patches.

## CI and releases

GitHub Actions builds and tests Linux x64, Windows x64, Intel macOS and ARM macOS.
It publishes CI artifacts, merges a universal Mac archive, and tests that archive
on both architectures. A `v<VERSION>` tag creates a **draft** GitHub release only
after all checks pass, with platform archives, source archive and `SHA256SUMS`.
No signing secrets are required. Set `VERSION.txt` before creating a matching tag.

See [provenance](PROVENANCE.md), [runtime details](docs/runtime.md), and the
[hardware acceptance checklist](docs/hardware-acceptance.md).

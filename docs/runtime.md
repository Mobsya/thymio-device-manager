# Runtime and compatibility

The standalone executable preserves TDM protocol version 1, the original
FlatBuffers schema, discovery identifiers, single-instance lock and command-line
behavior. No public C++ SDK is installed. Client applications can continue using
their existing TDM bindings. Firmware updating still uses the original remote
firmware service; network availability is needed for firmware downloads.

Linux uses libusb explicitly, independent of whether libudev development packages
are installed. Aware uses native Avahi discovery. Avahi and its D-Bus service must
be available before starting the manager. macOS and Windows use their existing
serial discovery paths and Bonjour. Remote simulated devices may still connect
using the original protocol, but this project does not build a simulator.

The Windows archive contains the x64 Bonjour client as `bin/dnssd.dll`. Its source
is the file named `dnssd64.dll` in the original repository: the adjacent file named
`dnssd.dll` is 32-bit despite being in an x64 folder. Static linking is used for
Boost, OpenSSL and the MSVC runtime. The Bonjour system service is still required.

The initial archives are unsigned by a trusted publisher. Apple notarization,
Windows Authenticode, native installers, background-service setup, Linux ARM,
Windows ARM and Windows x86 are outside this first release.

The inherited device-manager reference is retained for feature documentation.
Some launcher-specific instructions there describe Thymio Suite rather than this
standalone package; use this project's README for launching and installing it.

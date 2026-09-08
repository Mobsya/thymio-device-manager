# Source provenance

This standalone project starts at version 1.0.0 and was extracted from
https://github.com/Mobsya/aseba at commit
`743251f62feeec1bffdbe93df2c5cb6749d39756` (Aseba 2.4.0).

Retained source groups: `aseba/thymio-device-manager`, `aseba/compiler`,
`aseba/common` excluding Qt's `about`, `aseba/flatbuffers`, and the relevant common,
message and AESL tests. The standalone firmware-upgrader main is omitted.
Internal Aseba version constants remain separate from the standalone version.

The root CMake files, dependency recipes, Make interface, CI workflows, packaging
and additional tests belong to this extraction. Existing source notices and
`authors.txt` are retained. See `license.txt` for the inherited LGPL v3 text.

`dependencies.lock.json` records immutable source revisions and SHA-256 checksums.
In particular, aware, FlatBuffers and libusb retain Mobsya's revisions. Belle,
Catch2 and Bonjour SDK inputs are fetched as individual files from the original
Aseba revision; the entire Aseba repository is never cloned as a build dependency.
Belle includes the existing Boost compatibility changes.

Catch2 remains pinned to 2.4.1. Configuration adapts its macOS debugger trap to
Clang's architecture-independent builtin in the generated header and disables
its legacy POSIX signal handler for compatibility with modern glibc. Downloaded
dependency inputs remain unchanged and checksum-verified.

Binary packages contain third-party notices. Source packages contain this project
and every fetched dependency input, including original third-party notices and
build recipes. System components (Avahi, Bonjour service, OS frameworks and build
tools) remain platform prerequisites.

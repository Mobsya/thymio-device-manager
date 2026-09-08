# Hardware acceptance

Automated CI uses no robot. Before declaring a hardware release verified, record
the OS, architecture, robot firmware, dongle firmware, executable version and
results for each platform below. Do not infer hardware success from compilation.

| Platform | USB discovery | Dongle discovery | Reconnection | Compile/run | Firmware update |
| --- | --- | --- | --- | --- | --- |
| Ubuntu 26.04 x64 | Pending | Pending | Pending | Pending | Pending |
| macOS Intel | Pending | Pending | Pending | Pending | Pending |
| macOS Apple Silicon | Pending | Pending | Pending | Pending | Pending |
| Windows 10/11 x64 | Pending | Pending | Pending | Pending | Pending |

1. Run the extracted release archive with platform prerequisites installed.
2. Connect a Thymio through USB and verify an existing TDM client discovers it.
3. Compile a short Aseba program, run it, stop it, and read a robot variable.
4. Disconnect/reconnect USB and confirm the device becomes available again.
5. Repeat through a wireless dongle, including multiple already-paired robots.
6. On a designated test robot, exercise the client's normal firmware-update flow
   and verify the version and reconnection afterwards.
7. Stop/restart the manager, and verify a second simultaneous instance is rejected.

Also run on the oldest supported OS versions where available; hosted CI runner
versions are newer than some of the deployment targets.

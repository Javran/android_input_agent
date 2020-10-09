Basically just `adb exec-out input ...` but with less latency, with the help of [monkeyrunner](https://developer.android.com/studio/test/monkeyrunner).

Environment variables:

- `INPUT_AGENT_PORT`: a valid port number, required
- `ADB_BIN`: Location to the `adb` binary, optional
  (will use whatever available in `PATH` by default)

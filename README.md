Basically just `adb exec-out input ...` but with less latency, with the help of [monkeyrunner](https://developer.android.com/studio/test/monkeyrunner).

Use `monkeyrunner` to execute `server.py`, which starts a TCP server on host machine.
You can then use any mechanism to talk to this server to send input events (only `tap` and `swipe` are supported for now)
to the mobile device.

# Environment variables

- `INPUT_AGENT_PORT`: a valid port number, required

# Protocol

The interaction between client and server are line-based.
Empty spaces are strip from input before parsing, and a response will return
with `\n` in the end.

## Commands

- `version`: check current protocol version.

  This is always `android_input_agent v0` for now.
  This command is useful to verify that this server is up and running
  with the expected protocol version.

- `tap <x> <y>`: simulate a tap, all numbers must be integers.

  Returns either `ok` or `failed`, after this command is attempted.


- `swipe <x1> <y1> <x2> <y2>[ duration]`: simulate a swipe, all numbers must be integer.

  Note that `duration` is optional and is in milliseconds.
  Returns either `ok` or `failed`, after this command is attempted.

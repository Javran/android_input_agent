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

- `screenshot all`: capture screen and send it back as PNG data chunk.

  Receives following bytes in that order:
  + `begin 0 <sz>\n`, in which `<sz>` is an integer indicating number of bytes
  + subsequent `<sz>` bytes are the content of the image.
  + `end 0\n`
  + `ok\n`

- `screenshot x0 y0 w0 h0[ x1 y1 w1 h1]`: capture screen but only send parts of it back.

  + there could be many `x,y,w,h` tuples following `screenshot` command.
  + suppose there are `n` tuples in total, images are sent in that order following a protocol similar to that of `screenshot all`:
  + `begin <i> <sz>\n`, in which `i` ranges from `0` to `n-1`.
  + payload of size `<sz>`
  + `end <i>\n` marking the end of this image.
  + after all images are sent, an `ok\n` is followed.

## Error recovery

You might encounter some boost of "Broken pipes" exceptions,
which is probably caused by interruption to connection with `adb`.
I've tried some methods without restarting monkeyrunner,
unfortunately none of those approaches seem to work.
Therefore the server simply quits with exit code `6`
(so that it can be distinguished from keyboard interrupts),
you might want to have your `aia` script to put this server in a loop like below:

```bash
for (( ; ; ))
do
    $MONKEY_RUNNER_BIN server.py
    if (($? != 6))
    then
       break
    fi
done
```

Yes it's sad that we have to do this, but I have little interest for now
to investigate into what the heck is going on with monkeyrunner.

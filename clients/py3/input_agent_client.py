import socket

from typing import List, Optional, Sequence, Tuple


# Rectangle, (x, y, w, h)
Rect = Tuple[int, int, int, int]

# Coord, (x, y)
Coord = Tuple[int, int]


class InputAgentClient:

  port: int

  socket = None  # type: Optional[socket.socket]

  # Stores bytes left from last socket.rect call.
  _buffer = b''  # type: bytes

  def __init__(self, port):
    self.port = port

  def ensureSocket(self):
    """Ensures that the socket object is created."""
    if self.socket is not None:
      return

    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.settimeout(5)
    addr = ('127.0.0.1', self.port)
    self.socket.connect(addr)

  def abortSocket(self):
    """Abandons current socket connection, if any.

    Due to the nature of the tool we built upon, server side crash could happen
    from time to time, in which case it is necessary to abort current connection
    to restart the state of the instance.
    """
    self._buffer = b''
    if self.socket is None:
      return
    try:
      self.socket.shutdown(socket.SHUT_RDWR)
      self.socket.close()
    except OSError:
      # when this method is called,
      # it is likely that the server side is broken,
      # so we ignore all socket related errors, which
      # should all be a sub-class of OSError.
      pass
    finally:
      self.socket = None

  def _sendCommand(self, cmd: str):
    """Sends a str command to server, newline should not be included."""
    self.ensureSocket()
    self.socket.sendall(f'{cmd}\n'.encode())

  def _recvResponse(self) -> str:
    """Receives a str response from server, newlines are stripped.

    Raises:
      AssertionError: if socket.recv() returns 0 bytes.
    """
    # note the lack of ensureSocket() call: in this protocol
    # every send is paired with a recv, and since all sends have already called
    # ensureSocket(), it is not necessary to do it here.
    if self._buffer:
      # Consume leftovers from last recv call. This is assuming that
      # a complete command is never broken into multiple chunks
      line, self._buffer = self._buffer.split(b'\n', 1)
    else:
      payload = self.socket.recv(1024)
      if not payload:
        # TODO: raise some proper exceptions here.
        assert False, 'Server error'
      line, self._buffer = payload.split(b'\n', 1)

    return line.decode()

  def _recvOkOrFailed(self):
    """Handles reception of either an 'ok' or 'failed' response from server."""
    msg = self._recvResponse()
    # TODO: proper exceptions
    if msg == 'ok':
      return
    elif msg == 'failed':
      self.abortSocket()
      assert False, 'Server side failure'
    else:
      assert False, f'Unrecognized response: {msg}'

  def verifyServer(self):
    """Verifies that the server is up and running with expected protocol version.

    Raises:
      AssertionError: if the protocol version string is unexpected.
    """
    self._sendCommand('version')
    msg = self._recvResponse()
    assert msg == 'android_input_agent v0', f'Unexpected version: {msg}'

  def commandTap(self, coord: Coord):
    """Sends a tap to mobile device.

    Args:
      coord: the coordinate to tap.
    """
    x, y = coord
    self._sendCommand(f'tap {x} {y}')
    self._recvOkOrFailed()

  def commandSwipe(self, coord0: Coord, coord1: Coord, duration: Optional[int]=None):
    """Sends a swipe to mobile device.

    Args:
      coord0: start coordination.
      coord1: end coordination.
      duration: an optional int indication duration of the swipe in milliseconds.
    """
    x0, y0 = coord0
    x1, y1 = coord1
    cmd = f'swipe {x0} {y0} {x1} {y1}'
    if duration is not None:
      cmd += f' {duration}'
    self._sendCommand(cmd)
    self._recvOkOrFailed()

  def _recvDataChunks(self, count: int) -> List[bytes]:
    results = []
    for i in range(count):
      resp = self._recvResponse()
      expected_prefix = f'begin {i} '
      assert resp.startswith(expected_prefix), f'Expect begin marker, but got {resp}'
      expected_size = int(resp[len(expected_prefix):])
      payload, self._buffer = self._buffer, b''
      while len(payload) < expected_size:
        diff = expected_size - len(payload)
        incr = self.socket.recv(diff, socket.MSG_WAITALL)
        payload += incr

      if len(payload) > expected_size:
        payload, self._buffer = payload[:expected_size], payload[expected_size:]

      results.append(payload)
      resp = self._recvResponse()
      assert resp == f'end {i}', f'Expect end marker but found: "{resp}"'
    self._recvOkOrFailed()
    return results

  def commandScreenshotAll(self) -> bytes:
    """Takes a screenshot of the mobile device.

    Returns:
      a bytes object representing bytes of the PNG image.
    """
    self._sendCommand('screenshot all')
    [img] = self._recvDataChunks(1)
    return img

  def commandScreenshotRects(self, rects: Sequence[Rect]) -> List[bytes]:
    """Takes a screenshot of the mobile device, and send cropped rectangles back.

    Args:
      rects: sequence of Rects representing rectangles to crop in the screenshot image.
    Returns:
      list of bytes objects representing bytes of the PNG images,
      this list is of the same length as input argument, ordering is preserved.
    """
    rect_nums = []
    for rect in rects:
      rect_nums += map(str, rect)
    cmd = f'screenshot {" ".join(rect_nums)}'
    self._sendCommand(cmd)
    return self._recvDataChunks(len(rects))


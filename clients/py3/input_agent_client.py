import socket


class InputAgentClient:

  socket = None
  buffer = b''

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
    self.buffer = b''
    if self.socket is None:
      return
    try:
      self.socket.shutdown(socket.SHUT_RDWR)
      self.socket.close()
    except:
      pass
    finally:
      self.socket = None

  def _sendCommand(self, cmd: str):
    self.ensureSocket()
    self.socket.sendall(f'{cmd}\n'.encode())

  def _recvResponse(self) -> str:
    if not self.buffer:
      payload = self.socket.recv(1024)
      if not payload:
        assert False, 'Server error'
      line, new_buffer = payload.split(b'\n', 1)
      msg = line.decode()
      self.buffer = new_buffer
    else:
      line, new_buffer = self.buffer.split(b'\n', 1)
      msg = line.decode()
      self.buffer = new_buffer

    return msg

  def _recvOkOrFailed(self):
    msg = self._recvResponse()
    if msg == 'ok':
      return
    elif msg == 'failed':
      self.abortSocket()
      assert False, 'Server side failure'
    else:
      assert False, f'Unrecognized response: {msg}'

  def verifyServer(self):
    self._sendCommand('version')
    msg = self._recvResponse()
    assert msg == 'android_input_agent v0', f'Unexpected version: {msg}'

  def commandTap(self, coord):
    x, y = coord
    self._sendCommand(f'tap {x} {y}')
    self._recvOkOrFailed()

  def commandSwipe(self, coord0, coord1, duration=None):
    x0, y0 = coord0
    x1, y1 = coord1
    cmd = f'swipe {x0} {y0} {x1} {y1}'
    if duration is not None:
      cmd += f' {duration}'
    self._sendCommand(cmd)
    self._recvOkOrFailed()

  def _recvDataChunks(self, count):
    results = []
    for i in range(count):
      resp = self._recvResponse()
      expected_prefix = f'begin {i} '
      assert resp.startswith(expected_prefix), f'Expect begin marker, but got {resp}'
      expected_size = int(resp[len(expected_prefix):])
      payload = self.buffer
      self.buffer = b''
      while len(payload) < expected_size:
        diff = expected_size - len(payload)
        incr = self.socket.recv(diff, socket.MSG_WAITALL)
        payload += incr

      if len(payload) > expected_size:
        payload, self.buffer = payload[:expected_size], payload[expected_size:]

      results.append(payload)
      resp = self._recvResponse()
      assert resp == f'end {i}', f'Expect end marker but found: "{resp}"'
    self._recvOkOrFailed()
    return results

  def commandScreenshotAll(self):
    self._sendCommand('screenshot all')
    [img] = self._recvDataChunks(1)
    return img

  def commandScreenshotRects(self, rects):
    rect_nums = []
    for rect in rects:
      rect_nums += map(str, rect)
    cmd = f'screenshot {" ".join(rect_nums)}'
    self._sendCommand(cmd)
    return self._recvDataChunks(len(rects))


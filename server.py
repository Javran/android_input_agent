"""Host side server that parses the command and executes it on phone.

This is a Jython script that is supposed to be executed with monkeyrunner.
"""

import os
import re
import socket
import subprocess
import sys

from com.android.monkeyrunner import MonkeyRunner, MonkeyDevice

from java.util.logging import Level, Logger, StreamHandler, SimpleFormatter
from java.io import ByteArrayOutputStream


RE_TAP = re.compile(r'^tap (\d+) (\d+)$')
RE_SWIPE = re.compile(r'^swipe (\d+) (\d+) (\d+) (\d+)(?: (\d+))?$')
RE_SCREENSHOT_LIST = re.compile(r'^screenshot( (\d+) (\d+) (\d+) (\d+))+$')

global errors, device, logger
errors = None
device = None
logger = None


def parse_coord(raw_x, raw_y):
  return int(raw_x, base=10), int(raw_y, base=10)


def parse_command(raw):
  raw = raw.strip()
  if raw == 'version':
    return 'version', []

  r = RE_TAP.match(raw)
  if r is not None:
    return 'tap', [parse_coord(r.group(1), r.group(2))]

  r = RE_SWIPE.match(raw)
  if r is not None:
    if r.group(5) is None:
      duration = None
    else:
      duration = int(r.group(5), base=10)
    return 'swipe', [parse_coord(r.group(1), r.group(2)),
                     parse_coord(r.group(3), r.group(4)),
                     duration
                     ]
  if raw.startswith('screenshot'):
    if raw == 'screenshot all':
      return 'screenshot', ['all']
    if RE_SCREENSHOT_LIST.match(raw):
      nums = map(lambda x: int(x, base=10), raw.split(' ')[1:])
      rects = []
      while nums:
        (x,y,w,h), nums = nums[:4], nums[4:]
        rects.append((x,y,w,h))
      return 'screenshot', rects

  return None


# cargoculted from https://stackoverflow.com/a/822788/315302
def socket_line_split(s):
  buf = s.recv(8192)
  buffering = True
  while buffering:
    if '\n' in buf:
      (line, buf) = buf.split('\n', 1)
      yield line.strip()
    else:
      more = s.recv(8192)
      if not more:
        buffering = False
      else:
        buf += more
  if buf:
    yield buf


def perform_action(device, action, conn):
  cmd, args = action
  if cmd == 'version':
    conn.sendall('android_input_agent v0\n')
    return True
  try:
    if cmd == 'tap':
      [(x,y)] = args
      device.touch(x,y, MonkeyDevice.DOWN_AND_UP)
    elif cmd == 'swipe':
      [coord_start, coord_end, duration] = args
      if duration is None:
        duration = 0.3
      else:
        # the protocol is meant to mimic `adb exec-out input` command,
        # in which duration is given as milliseconds,
        # thus this conversion, as monkeyrunner uses seconds.
        duration = duration / 1000.0
      device.drag(coord_start, coord_end, duration, 5)
    elif cmd == 'screenshot':
      img = device.takeSnapshot()

      if args == ['all']:
        img_list = [img]
      else:
        img_list = []
        for rect in args:
          img_list.append(img.getSubImage(rect))

      for (i, cur_img) in enumerate(img_list):
        payload = cur_img.convertToBytes('png')
        conn.sendall('begin %d %d\n' % (i, len(payload)))
        conn.sendall(payload)
        conn.sendall('end %d\n' % i)
    if errors.size():
      conn.sendall('failed\n')
      return False
    else:
      conn.sendall('ok\n')
      return True
  except:
    e = sys.exc_info()[0]
    print(e)
    conn.sendall('failed\n')
    return False


def main(prefer_port):
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.bind(('127.0.0.1', prefer_port))
  s.listen(5)
  # note that prefer_port might not be the port we end up using,
  # this could happen when prefer_port is 0, in which it is the OS assigning a port to us.
  host, port = s.getsockname()
  print('Listening on %s:%s ...' % (host, port))

  failed = False
  while not failed:
    conn, (c_host, c_port) = s.accept()
    print('Accepted connection from %s:%s' % (c_host, c_port))
    try:
      for line in socket_line_split(conn):
        action = parse_command(line)
        if action is None:
          conn.sendall('invalid\n')
          continue
        cmd, args = action
        if not perform_action(device, action, conn):
          failed = True
          break
    except:
      pass
    print('Closing connection from %s:%s' % (c_host, c_port))
    conn.close()
  s.close()
  if failed:
    # It seems like some state is not set properly, as once it fails,
    # killing monkey on mobile side doesn't seem to work.
    # so instead, let's just let whatever starts this server do the restart.
    print('Something unrecoverable happened. commiting suicide...')
    sys.exit(6)


if __name__ == '__main__':
  port = int(os.getenv('INPUT_AGENT_PORT'), base=10)

  # One annoyance of using monkeyrunner is that whatever process is up on the phone side
  # does not terminate after it is disconnected, this does not raise any exception
  # but you can see from the output that there are broken pipes.
  # Therefore as a shotgun approach, we need to make sure that previous monkeyrunner process
  # on phone is killed before we attempt any connection.
  # See: https://stackoverflow.com/a/28063652/315302
  # It is intentional that this process call is unchecked.
  subprocess.call(['adb', 'exec-out', 'killall', 'com.android.commands.monkey'])

  # https://stackoverflow.com/a/28070375/315302
  errors = ByteArrayOutputStream(100)
  logger = Logger.getLogger('com.android.chimpchat.adb.AdbChimpDevice')
  logger.addHandler(StreamHandler(errors, SimpleFormatter()))

  print('Waiting for adb connection...')
  device = MonkeyRunner.waitForConnection()
  main(port)

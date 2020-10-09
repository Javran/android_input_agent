"""Host side server that parses the command and executes it on phone.

This is a Jython script that is supposed to be executed with monkeyrunner.
"""

import os
import re
import socket
import subprocess
import sys

from com.android.monkeyrunner import MonkeyRunner, MonkeyDevice


RE_TAP = re.compile(r'^tap (\d+) (\d+)$')
RE_SWIPE = re.compile(r'^swipe (\d+) (\d+) (\d+) (\d+)(?: (\d+))?$')


def parse_coord(raw_x, raw_y):
  return int(raw_x, base=10), int(raw_y, base=10)


def parse_command(raw):
  raw = raw.strip()
  if raw == 'check':
    return 'check', []

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


def perform_action(device, action):
  cmd, args = action
  if cmd == 'check':
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
        duration = duration / 1000.0
      device.drag(coord_start, coord_end, duration, 5)
    return True
  except:
    e = sys.exc_info()[0]
    print(e)
    return False


def main(port, device):
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.bind(('127.0.0.1', port))
  s.listen(5)
  print('Bound and listening ...')
  conn, addr = s.accept()
  print('Connected by %s' % str(addr))
  for line in socket_line_split(conn):
    action = parse_command(line)
    if action is None:
      conn.sendall('invalid\n')
      continue
    cmd, args = action
    if cmd == 'check':
      conn.sendall('ok\n')
    else:
      if perform_action(device, action):
        conn.sendall('ok\n')
      else:
        conn.sendall('failed\n')

  conn.close()
  s.close()


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

  print('Waiting for adb connection...')
  device = MonkeyRunner.waitForConnection()
  main(port, device)

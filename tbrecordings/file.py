import os

class File(object):
  def __init__(self, filename, path='', extension='', type='media', ts=0, duration=0):
    self.type = type
    if extension == '':
      self.filename, self.extension = os.path.splitext(filename)
    else:
      self.filename = filename
      self.extension = extension
    self.path = path
    self.fullname = os.path.join(path, self.filename + self.extension)
    self.ts = ts
    self.duration = duration
    self.splits = 0

  def slice(self, start_ts=0, stop_ts=0):
    start_ts -= self.ts
    stop_ts -= self.ts
    start_ts = max(0, start_ts)
    stop_ts = max(start_ts, stop_ts)
    if self.type == 'slide':
      file = File(self.filename, extension=self.extension, path=self.path, type=self.type, ts=start_ts, duration=stop_ts - start_ts)
      return file, ''
    else:
      file = File(self.filename + '_%d' % self.splits, extension=self.extension, path=self.path, type=self.type, ts=start_ts, duration=stop_ts - start_ts)
      cmd = "ffmpeg -y -i %s" % self.fullname
      cmd += " -ss %.3f -t %.3f -sn %s" %(1e-3 * start_ts, 1e-3 * (stop_ts - start_ts), file.fullname)
      self.splits += 1

    return file, cmd
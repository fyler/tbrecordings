import os
import subprocess
import logging
import sys
import re
import json
from file import File
from PIL import Image

logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def shell_cmd(cmd):
  logging.info(cmd)
  proc = subprocess.Popen(
    [cmd], 
    stdout=subprocess.PIPE, 
    stderr=subprocess.PIPE, 
    shell=True
  )
  return proc.communicate()

class ActionError(Exception):
  def __init__(self, mismatch):
    Exception.__init__(self, mismatch)

class Action(object):
  def __init__(self, actions, *args, **kwargs):
    if not 'path' in kwargs:
      self.path = None
    else:
      self.path = kwargs['path']
    self.out = None
    if isinstance(actions, list):
      self.input_actions = actions
    else:
      self.input_actions = [actions]
    self.input_args = args
    self.performed = False

  def output(self):
    return self.out

  def command(self):
    return self.cmd

  def perform(self):
    if self.out is None:
      if len(self.input_actions) > 0:
        self.input = []
        if len(self.input_args) > 0:
          assert len(self.input_args) == len(self.input_actions)
          for i in xrange(len(self.input_actions)):
            if not self.input_actions[i].performed:
              self.input_actions[i].perform()
            self.input.append(self.input_actions[i].output(self.input_args[i]))
        else:
          for i in xrange(len(self.input_actions)):
            if not self.input_actions[i].performed:
              self.input_actions[i].perform()
            self.input.append(self.input_actions[i].output())  
      self.cmd = self._build_cmd()

    if not self.performed:
      out, err = shell_cmd(self.cmd)    
      self.check(out, err)
      self.performed = True

class Download(Action):
  def __init__(self, url, path='', name='pres', extension='.pdf'):
    self.out = File(name, path=path, extension=extension, type='presentation')
    self.cmd = 'wget %s -O %s' % (url, self.out.fullname)
    self.performed = False

  def _bulid_cmd(self):
    return self.cmd

  def check(self, out, err):
    if not os.path.exists(self.out.fullname):
      raise ActionError('Downloading failed: %s' % err)

class GetSlides(Action):
  def __init__(self, action, path=None):
    super(GetSlides, self).__init__(action, path=path)

  def _build_cmd(self):
    self.out = {}
    input = self.input[0]
    if self.path is None:
      self.path = input.path
    self.mask = re.compile(ur'^%s_[1-9][0-9]*\.png$' % input.filename)
    cmd = 'gs -sDEVICE=pngalpha -o ' 
    cmd += os.path.join(self.path, '%s_%%d.png' % input.filename)
    cmd += ' -sDEVICE=pngalpha -r144 %s' % self.input[0].fullname
    return cmd

  def output(self, slide):
    if slide > self.slides:
      slide = self.slides
    return self.out[slide]

  def check(self, out, err):
    files = os.listdir(self.path)
    self.slides = 0
    for file in files:
      if not re.match(self.mask, file) is None:
        self.slides += 1
    if self.slides == 0:
      raise ActionError('Generation slides failed: %s' % err)
    cmd = 'ffprobe -v quiet -print_format json -show_streams '
    for i in xrange(self.slides):
      self.out[i + 1] = File('%s_%d' % (self.input[0].filename, i + 1), path=self.path, extension='.png', type='slide')
      with Image.open(self.out[i + 1].fullname) as im:
        w, h = im.size
        im.crop((0, 0, w / 2 * 2, h / 2 * 2)).save(self.out[i + 1].fullname)
        self.out[i + 1].set_meta('width', w / 2 * 2)
        self.out[i + 1].set_meta('height', h / 2 * 2)

class Prepare(Action):
  def __init__(self, action, name=None):
    super(Prepare, self).__init__(action)
    if isinstance(action, File):
      self.input_actions = []
      self.input = [action]

  def _build_cmd(self):
    file = self.input[0]
    if file.type == 'media':
      self.out = File(file.filename, path=os.path.join(file.path, 'tmp'), extension='.mp4', ts=file.ts)
      cmd = 'ffmpeg -i %s ' % file.fullname
      cmd += '-filter_complex "[0:v]setpts=PTS-STARTPTS" '
      cmd += '-c:v libx264 -keyint_min 15 -g 15 '
      cmd += '-c:a libfdk_aac '
      cmd += self.out.fullname
    elif file.type == 'presentation' and file.extension != '.pdf':
      cmd = 'libreoffice --headless --invisible --convert-to pdf --outdir %s %s' % (file.path, file.fullname)
      self.out = File(file.filename, path=file.path, extension='.pdf', ts=file.ts)
    elif file.type == 'slide' and (file.meta['width'] % 2 == 1 or file.meta['height'] % 2 == 1):
      self.out = File(file.filename + 'even', path=file.path, extension='.png', ts=file.ts, duration=file.duration)
      cmd = 'ffmpeg -i %s ' % file.fullname
      cmd += '-filter_complex "[0:v]crop=%d:%d" ' % (file.meta['width'] / 2 * 2, file.meta['height'] / 2 * 2)
      cmd += self.out.fullname
    else:
      cmd = ''
      self.out = file
    return cmd

  def check(self, out, err):
    if not os.path.exists(self.out.fullname):
      raise ActionError('Preparing failed: %s' % err)

class Slice(Action):
  def __init__(self, action, *args, **kwargs):
    default = {'start_ts': 0, 'stop_ts': 0}
    default.update(kwargs)
    self.out = None
    self.input_actions = [action]
    self.input_args = args
    self.start_ts = default['start_ts']
    self.stop_ts = default['stop_ts']
    self.performed = False

  def _build_cmd(self):
    file = self.input[0]
    out, cmd = file.slice(self.start_ts, self.stop_ts)
    self.out = out
    return cmd

  def check(self, out, err):
    if not os.path.exists(self.out.fullname):
      raise ActionError('Slicing failed: %s' % err)

class Render(Action):
  def __init__(self, actions, name='render'):
    super(Render, self).__init__(actions)
    self.name = name

  def _build_cmd(self):
    files = self.input
    self.out = File(self.name, path=files[0].path, extension='.mp4', ts=files[0].ts, duration=files[0].duration)
    media = []
    slides = []
    for file in files:
      if file.type == 'media':
        media.append(file)
      if file.type == 'slide':
        slides.append(file)

    cmd = 'ffmpeg '
    for slide in slides:
      cmd += '-loop 1 -i %s ' % slide.fullname
    slide_streams = len(slides)
    if slide_streams == 0:
      cmd += '-f lavfi -i color=color=gray:r=24:s=%dx%d' % (w, h)
      slide_streams += 1

    for medium in media: 
      cmd += '-i %s ' % medium.fullname
    filters = []
    f = '[0:v] pad=iw+320:ih:color=gray'
    if len(media) > 0:
      f += ' [bg0]'
      filters.append(f)
      for i, medium in enumerate(media):
        filters.append('[%d:v]setpts=PTS-STARTPTS[f%d]' % (slide_streams + i, i))
      for i, medium in enumerate(media):
        filters.append('[bg%d][f%d]overlay=main_w-overlay_w:%d*overlay_h:shortest=1[bg%d]' % (i, i, i, i + 1))
      filters.append(''.join(['[%d:a]' % (i + 1) for i in xrange(len(media))]) + 'amix=inputs=%d [aout]' % len(media))
      cmd += '-filter_complex "' + '; '.join(filters) + '" '
      cmd += '-map "[bg%d]" -map "[aout]" ' % len(media)
    else:
      filters.append(f)
      cmd += '-t %.3f ' % (slides[0].duration / 1000.)
      cmd += '-f lavfi -i anullsrc=r=16000 -t %.3f ' % (slides[0].duration / 1000.)
      cmd += '-filter_complex "' + '; '.join(filters) + '" '
      cmd += '-c:a libfdk_aac '

    cmd += self.out.fullname
    return cmd

  def check(self, out, err):
    if not os.path.exists(self.out.fullname):
      raise ActionError('Rendering failed: %s' % err)

class Concat(Action):
  def __init__(self, actions, name='recording', path=None):
    self.name = name
    super(Concat, self).__init__(actions, path=path)

  def _build_cmd(self):
    files = self.input
    if self.path is None:
      path=files[0].path
    else:
      path=self.path
    self.out = File(self.name, path=path, extension='.mp4')
    n = len(files)
    cmd = 'ffmpeg '
    cmd += ' '.join(['-i ' + file.fullname for file in files])
    cmd += ' -filter_complex '
    cmd += '"' + ' '.join(['[%d:v] [%d:a]' % (i, i) for i in xrange(n)])
    cmd += ' concat=n=%d:v=1:a=1 [v] [s]" -map "[v]" -map "[s]" %s' % (n, self.out.fullname)
    return cmd

  def check(self, out, err):
    if not os.path.exists(self.out.fullname):
      raise ActionError('Concatination failed: %s' % err)

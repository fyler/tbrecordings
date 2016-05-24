import os
from file import File

class Action:
  def output(self):
    return self.out
  def command(self):
    return self.cmd
  def perform(self):
    os.system(self.cmd)  

class Download(Action):
  def __init__(self, url, path='', name='pres'):
    self.out = File(name, path=path, extension='.pdf', type='presentation')
    self.cmd = 'wget %s -O %s' % (url, self.out.fullname)

class GetSlides(Action):
  def __init__(self, file):
    self.input = file
    self.out = {}
    name = os.path.join(self.input.path, self.input.filename)
    self.cmd = 'gs -sDEVICE=pngalpha -o '
    self.cmd += '%s_%%d.png -sDEVICE=pngalpha -r144 %s' % (name, self.input.fullname) 

  def output(self, slide):
    if slide in self.out:
      return self.out[slide]
    else:
      self.out[slide] = File('%s_%d' % (self.input.filename, slide + 1), path=self.input.path, extension='.png', type='slide')
      return self.out[slide]

class Prepare(Action):
  def __init__(self, file):
    if file.type == 'media':
      output = File(file.filename, path=os.path.join(file.path, 'tmp'), extension='.mp4', ts=file.ts)
      self.cmd = 'ffmpeg -i %s ' % file.fullname
      self.cmd += '-c:v libx264 -keyint_min 15 -g 15 '
      self.cmd += '-c:a libfdk_aac '
      self.cmd += output.fullname
      self.out = output
    else:
      self.out = file
      self.cmd = ''

class Slice(Action):
  def __init__(self, file, start_ts, stop_ts):
    self.input = file
    out, cmd = file.slice(start_ts, stop_ts)
    self.out = out
    self.cmd = cmd

class Render(Action):
  def __init__(self, files, name='render'):
    self.input = files
    self.out = File(name, path=files[0].path, extension='.mp4', ts=files[0].ts, duration=files[0].duration)
    media = []
    slides = []
    for file in files:
      if file.type == 'media':
        media.append(file)
      if file.type == 'slide':
        slides.append(file)

    self.cmd = 'ffmpeg '
    for slide in slides:
      self.cmd += '-loop 1 -i %s ' % slide.fullname
    slide_streams = len(slides)
    if slide_streams == 0:
      self.cmd += '-f lavfi -i color=color=gray:r=24:s=%dx%d' % (w, h)
      slide_streams += 1

    for medium in media: 
      self.cmd += '-i %s ' % medium.fullname
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
      self.cmd += '-filter_complex "' + '; '.join(filters) + '" '
      self.cmd += '-map "[bg%d]" -map "[aout]" ' % len(media)
    else:
      filters.append(f)
      self.cmd += '-t %.3f ' % (slides[0].duration / 1000.)
      self.cmd += '-f lavfi -i anullsrc=r=16000 -t %.3f ' % (slides[0].duration / 1000.)
      self.cmd += '-filter_complex "' + '; '.join(filters) + '" '
      self.cmd += '-c:a libfdk_aac '

    self.cmd += self.out.fullname

class Concat(Action):
  def __init__(self, files, name='recording', path=''):
    self.input = files
    self.out = File(name, path=os.path.join(files[0].path, path), extension='.mp4')
    n = len(files)
    self.cmd = 'ffmpeg '
    self.cmd += ' '.join(['-i ' + file.fullname for file in files])
    self.cmd += ' -filter_complex '
    self.cmd += '"' + ' '.join(['[%d:v] [%d:a]' % (i, i) for i in xrange(n)])
    self.cmd += ' concat=n=%d:v=1:a=1 [v] [s]" -map "[v]" -map "[a]" %s' % (n, self.out.fullname)
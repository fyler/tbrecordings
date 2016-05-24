import struct
import json
import sys
import os
from amfast.decoder import Decoder
from action import Download, GetSlides, Prepare, Slice, Render, Concat
from file import File

decoder = Decoder(amf3=True)


class Recording(object):
    
  def __init__(self, index='index.json'):

    self.path, index = os.path.split(index)
    with open(index, 'r') as f:
      index = json.loads(f.read())
    self.duration = index['duration']
    self.chunks = index['chunks']
    self.streams = index['streams']
    self.snapshot = index['snapshots'][0]['name']
    self.actions = []
    self.files = []
    self.events = []
    self.counter = 0
    self.docs = {}
    
    tmp = os.path.join(self.path, 'tmp')

    if not os.path.exists(tmp):
      os.makedirs(tmp)

    with open(self.snapshot, 'rb') as f:
      snapshot = f.read()
      ts, size = struct.unpack('>ii', snapshot[0:0 + 8])

    obj = decoder.decode(snapshot[8:size + 8])

    for doc in obj['documents']:
      self.docs[doc['id']] = {'url': doc['file']['url'], 'slide': doc['data']['slide'], 'active': False}
     
    workplace = ''
    for instance in obj['layout']['elements']:
      if instance['module'] == 'docs':
        workplace = 'workplace::%d' % instance['id']

    slides = {}

    if obj[workplace]['type'] == 'active':
      self.current_doc = obj[workplace]['data']['id']
      self.docs[self.current_doc]['active'] = True
      download_doc = Download(self.docs[self.current_doc]['url'], path=tmp, name='%d' % self.current_doc)
      self.actions.append([download_doc])
      slides[self.current_doc] = GetSlides(download_doc.output())
      self.actions.append([slides[self.current_doc]])

    prepare_streams = []
    for stream in self.streams:
      start_ts = stream['start_ts']
      finish_ts = stream['finish_ts']
      file = File(stream['name'], extension='.flv', path=self.path, type=stream['type'], ts=start_ts)
      prepare_stream = Prepare(file)
      prepare_streams.append(prepare_stream)
      id = self.add_file(prepare_stream.output())
      self.events.append((start_ts, id, 1))
      self.events.append((finish_ts, id, -1))
    self.actions.append(prepare_streams)

    if self.current_doc:
      file = slides[self.current_doc].output(self.docs[self.current_doc]['slide'])
      id = self.add_file(file)
      self.events.append((0, id, 1))
      doc = 'document::%d' % self.current_doc

    for chunk in self.chunks:
      with open(chunk['name'], 'rb') as f:
        chunk_data = f.read()
        pointer = 0
        while pointer < len(chunk_data):
            ts, size = struct.unpack('>ii', chunk_data[pointer:pointer + 8])
            obj = decoder.decode(chunk_data[pointer + 8:pointer + size + 8])
            if obj['type'] == doc:
                if obj['data']['method'] == 'goToSlide':
                    file = slides[self.current_doc].output(obj['data']['data'][0])
                    print 'goToSlide', obj['data']['data'][0] + 1
                    id = self.add_file(file)
                    id_prev = self.events[-1][1]
                    self.events.append((ts, id_prev, -1))
                    self.events.append((ts, id, 1))
            pointer += size + 8

    self.events.sort()
    current_events = set()
    current_ts = self.events[0][1]
    slices = []
    renders = []
    parts = []
    part_ind = 0
    for event in self.events:
      if event[0] > current_ts:
        current_slices = [Slice(self.files[id], current_ts, event[0]) for id in current_events]
        slices += current_slices
        render = Render([slice.output() for slice in current_slices], name='part_%d' % part_ind)
        part_ind += 1
        renders.append(render)
        parts.append(render.output())
        current_ts = event[0]
      if event[2] > 0:
        current_events.add(event[1])
      else:
        current_events.remove(event[1])

    self.actions.append(slices)
    self.actions.append(renders)
    self.actions.append([Concat(parts, path="..")])
    for stage in self.actions:
      for action in stage:
        print action.command()
    
  def add_file(self, file):
    self.files.append(file)
    self.counter += 1
    return self.counter - 1

  def assemble(self):
    for stack_cmd in self.actions:
      for cmd in stack_cmd:
        cmd.perform()
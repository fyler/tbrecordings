import struct
import json
import sys
import os
import shutil
from amfast.decoder import Decoder
from action import Download, GetSlides, Prepare, Slice, Render, Concat
from file import File

decoder = Decoder(amf3=True)


class Recording(object):
    
  def __init__(self, index='index.json'):
    self.path, _ = os.path.split(index)
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

    with open(os.path.join(self.path, self.snapshot), 'rb') as f:
      snapshot = f.read()
      ts, size = struct.unpack('>ii', snapshot[0:0 + 8])

    obj = decoder.decode(snapshot[8:size + 8])

    for doc in obj['documents']:
      self.docs[doc['id']] = {
        'url': doc['file']['url'], 
        'extension': doc['file']['extension'],
        'slide': doc['data']['slide'] if 'slide' in doc['data'] else 0, 
        'active': False
      }
   
    workplace = ''
    for instance in obj['layout']['elements']:
      if instance['module'] == 'docs':
        workplace = 'workplace::%d' % instance['id']

    slides = {}

    if obj[workplace]['type'] == 'active':
      self.current_doc = obj[workplace]['data']['id']
      self.docs[self.current_doc]['active'] = True
      doc = Download(
        self.docs[self.current_doc]['url'], 
        path=tmp, 
        name='%d' % self.current_doc, 
        extension='.' + self.docs[self.current_doc]['extension']
      )
      self.actions.append([doc])
      if self.docs[self.current_doc]['extension'] != '.pdf':
        doc = Prepare(doc)
        self.actions.append([doc])
      slides[self.current_doc] = GetSlides(doc)
      self.actions.append([slides[self.current_doc]])

    prepare_streams = []
    for stream in self.streams:
      start_ts = stream['start_ts']
      finish_ts = stream['finish_ts']
      file = File(stream['name'], extension='.flv', path=self.path, type=stream['type'], ts=start_ts)
      prepare_stream = Prepare(file)
      prepare_streams.append(prepare_stream)
      id = self.add_file(prepare_stream)
      self.events.append((start_ts, id, 1))
      self.events.append((finish_ts, id, -1))
    self.actions.append(prepare_streams)

    if self.current_doc:
      file = slides[self.current_doc]
      id = self.add_file((file, self.docs[self.current_doc]['slide'] + 1))
      self.events.append((0, id, 1))
      doc = 'document::%d' % self.current_doc

    for chunk in self.chunks:
      with open(os.path.join(self.path, chunk['name']), 'rb') as f:
        chunk_data = f.read()
        pointer = 0
        while pointer < len(chunk_data):
            ts, size = struct.unpack('>ii', chunk_data[pointer:pointer + 8])
            obj = decoder.decode(chunk_data[pointer + 8:pointer + size + 8])
            if obj['type'] == doc:
                if obj['data']['method'] == 'goToSlide':
                    id = self.add_file((slides[self.current_doc], obj['data']['data'][0] + 1))
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
        current_slices = [
          Slice(self.files[id][0], self.files[id][1], start_ts=current_ts, stop_ts=event[0])
          if isinstance(self.files[id], tuple) else 
          Slice(self.files[id], start_ts=current_ts, stop_ts=event[0]) 
          for id in current_events]
        slices += current_slices
        render = Render([slice for slice in current_slices], name='part_%d' % part_ind)
        part_ind += 1
        renders.append(render)
        parts.append(render)
        current_ts = event[0]
      if event[2] > 0:
        current_events.add(event[1])
      else:
        current_events.remove(event[1])

    self.actions.append(slices)
    self.actions.append(renders)
    self.finish = Concat(parts, path=self.path)
    self.actions.append([self.finish])
    
  def add_file(self, action):
    self.files.append(action)
    self.counter += 1
    return self.counter - 1

  def assemble(self):
    self.finish.perform()
    return self.finish.output().fullname

  def clear(self):
    shutil.rmtree(os.path.join(self.path, 'tmp'))


import recording
import shutil
import os
import sys
import json
import logging
import tempfile
import boto3
import re
import traceback
from action import ActionError

logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

p_s3_1 = re.compile(ur'^https?:\/\/([a-zA-Z0-9_\.]+)\.s3\.amazonaws\.com\/([a-zA-Z0-9_\.\/]+)\/(\w+\.json)$')
p_s3_2  = re.compile(ur'^s3:\/\/([\w\.]+)\/(.*)\/(\w+\.json)$')

class InputBase(object):
  def fetch(self):
    pass
  def clear(self):
    pass 
  def description(self):
    pass
  def generate_output(self):
    pass

class OutputBase(object):
  def upload(self):
    pass
  def description(self):
    pass

class InputS3(InputBase):
  def __init__(self, bucket, prefix, index='index.json'):
    self.__bucket = bucket
    self.__prefix = prefix
    self.__index = index
    self.__tmp = tempfile.mkdtemp()

  def fetch(self):
    logging.info('Fetch files from s3 to %s', self.__tmp)
    client = boto3.client('s3')
    index_json = os.path.join(self.__tmp, 'index.json')
    client.download_file(self.__bucket, os.path.join(self.__prefix, self.__index), index_json)
    with open(index_json, 'r') as f:
      index = json.loads(f.read())
      for entities in ['chunks', 'snapshots', 'streams']:
        for entity in index[entities]:
          client.download_file(
            self.__bucket, 
            os.path.join(self.__prefix, entity['name'] + ('.flv' if entities == 'streams' else '')), 
            os.path.join(self.__tmp, entity['name'] + ('.flv' if entities == 'streams' else ''))
          )
    return index_json

  def clear(self):
    shutil.rmtree(self.__tmp)

  def generate_output(self):
    return OutputS3(self.__bucket, self.__prefix)

  def description(self):
    return 'http://' + self.__bucket + '.s3.amazonaws.com/' + self.__prefix + '/' + self.__index

class OutputS3(OutputBase):
  def __init__(self, bucket, prefix):
    self.__bucket = bucket
    self.__prefix = prefix

  def upload(self, recording):
    client = boto3.client('s3')
    client.upload_file(src, self.__bucket, os.path.join(self.__prefix, 'recording.mp4'), ExtraArgs={'ACL': 'public-read'})

  def description(self):
    return 'http://' + self.__bucket + '.s3.amazonaws.com/' + self.__prefix + '/recording.mp4'

class Input(object):
  def __init__(self, input):
    match_s3_1 = re.search(p_s3_1, input)
    match_s3_2 = re.search(p_s3_2, input)
    if not match_s3_1 is None:
      self.processor = InputS3(match_s3_1.group(1), match_s3_1.group(2), match_s3_1.group(3))
    elif not match_s3_2 is None:
      self.processor = InputS3(match_s3_2.group(1), match_s3_2.group(2), match_s3_2.group(3))

  def fetch(self):
    return self.processor.fetch()

  def clear(self):
    self.processor.clear()

  @property
  def description(self):
    return self.processor.description()
  

class Output(object):
  def __init__(self, output, input_processor):
    if not output is None:
      pass
    else:
      self.processor = input_processor.processor.generate_output()

  def upload(self):
    self.processor.upload()

  @property
  def description(self):
    return self.processor.description()

class NotifyBase(object):
  def __init__(self, input_desc, output_desc):
    self.__input_desc = input_desc
    self.__output_desc = output_desc
  def error(self, error_msg):
    pass
  def success(self):
    pass

class NotifyLocal(NotifyBase):    
  def error(self, error_msg):
    logging.error(error_msg)
  def success(self):
    logging.info('Success!')

class NotifySNS(object):
  def __init__(self, arn, input_desc, output_desc):
    self.__input_desc = input_desc
    self.__output_desc = output_desc
    self.__arn = arn

  def __notify(self, msg):
    client = boto3.client('sns')
    subject = 'TbRecording'
    response = client.publish(
        TargetArn = self.__arn,
        Message = msg,
        Subject = subject
    )

  def error(self, error_msg):
    msg = 'Convertation is failed: %s' % self.__input_desc + '\n' + error_msg + '\n'
    self.__notify(msg)

  def success(self):
    msg = 'Success! Input: %s' % self.__input_desc + '\n' + self.__output_desc + '\n'

class Notify(object):
  def __init__(self, sns, input_desc, output_desc):
    if not sns is None:
      self.__notifier = NotifySNS(sns, input_desc, output_desc)
    else:
      self.__notifier = NotifyLocal(input_desc, output_desc)

  def error(self, error_msg):
    self.__notifier.error(error_msg)

  def success(self):
    self.__notifier.success()

class Processor(object):
  def __init__(self, input, output=None, sns=None):
    self.__input = Input(input)
    self.__output = Output(output, self.__input)
    self.__notify = Notify(sns, self.__input.description, self.__output.description) 

  def __process(self):
    index = self.__input.fetch()
    rec = recording.Recording(index)
    self.recording = rec.assemble()

  def process(self):
    try:
      self.__process()
    except ActionError, e:
      error_msg = str(e) + '\n' + traceback.format_exc()
      self.__notify.error(error_msg)
      self.__input.clear()
    except Exception, e:
      error_msg = str(e) + '\n' + traceback.format_exc()
      self.__notify.error(error_msg)
      self.__input.clear()
    else:
      self.__output.upload(self.recording)
      self.__notify.success()
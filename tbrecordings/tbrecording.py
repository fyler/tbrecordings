import recording
import shutil
import os
import sys
import json
import logging
import tempfile
import argparse
import boto3
import re
from action import ActionError

logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

p = re.compile(ur'^s3://(\w*)/(.*)')

def fetch(tmp, bucket, prefix):
  logging.info('Fetch files from s3 to %s', tmp)
  client = boto3.client('s3')
  client.download_file(bucket, os.path.join(prefix, 'index.json'), os.path.join(tmp, 'index.json'))
  with open(os.path.join(tmp, 'index.json'), 'r') as f:
    index = json.loads(f.read())
    for entities in ['chunks', 'snapshots', 'streams']:
      for entity in index[entities]:
        client.download_file(
          bucket, 
          os.path.join(prefix, entity['name'] + ('.flv' if entities == 'streams' else '')), 
          os.path.join(tmp, entity['name'] + ('.flv' if entities == 'streams' else ''))
        )

def upload(src, bucket, prefix):
  logging.info('Upload %s to s3', src)
  client = boto3.client('s3')
  client.upload_file(src, bucket, os.path.join(prefix, 'recording.mp4'), ExtraArgs={'ACL': 'public-read'})

def notify(msg, arn):
  logging.info(arn)
  client = boto3.client('sns')
  subject = 'TbRecording'
  response = client.publish(
      TargetArn = arn,
      Message = msg,
      Subject = subject
  )

def main():
  parser = argparse.ArgumentParser(prog='tbrecording')
  parser.add_argument('-i', dest='input', default=None, help='URL or path to index.json')
  parser.add_argument('-o', dest='output', default=None, help='Place to store obtained recording')
  parser.add_argument('-sns', dest='sns', default=None, help='SNS')
  args = parser.parse_args()
  omode = 'local'
  opath = ''
  if not args.output is None:
    match = re.search(p, args.output)
    if match:
      omode = 's3'
      obucket = match.group(1)
      oprefix = match.group(2)
    else:
      opath = args.output
  if not args.input is None:
    match = re.search(p, args.input)
    if match:
      imode = 's3'
      ibucket = match.group(1)
      iprefix = match.group(2)
      if args.output is None:
        omode = 's3'
        obucket = ibucket
        oprefix = iprefix
    else:
      ipath = args.input     
  else:
    ipath='index.json'
  if imode == 's3':
    tmp = tempfile.mkdtemp()
    fetch(tmp, ibucket, iprefix)
    rec = recording.Recording(os.path.join(tmp, 'index.json'))
    try:
      path = rec.assemble()
    except ActionError as e:
      if not args.sns is None:
        msg = 'Convertation is failed: %s' % args.input + '\n'
        msg += str(ActionError)
        msg += '\n'
        notify(msg, args.sns)
      shutil.rmtree(tmp)
    else:
      if not args.sns is None:
        msg = 'Success! Input: %s' % args.input + '\n'
        if omode == 's3':
          msg += 'http://' + obucket + '.s3.amazonaws.com/' + oprefix + '/recording.mp4'
          msg += '\n'
        notify(msg, args.sns)
        
      if omode == 's3':
        upload(path, obucket, oprefix)
      shutil.rmtree(tmp)
from tbrecordings.processor import Processor
import argparse

def main():
  parser = argparse.ArgumentParser(prog='tbrecording')
  parser.add_argument('-i', dest='input', default=None, help='URL or path to index.json')
  parser.add_argument('-o', dest='output', default=None, help='Place to store obtained recording')
  parser.add_argument('-sns', dest='sns', default=None, help='SNS')
  args = parser.parse_args()
  
  if not args.input is None:
    processor = Processor(args.input, args.output, args.sns)
    processor.process()
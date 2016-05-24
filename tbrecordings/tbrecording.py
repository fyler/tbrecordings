import recording
import argparse

def main():
  parser = argparse.ArgumentParser(prog='tbrecording')
  parser.add_argument('-i', default='index.json')
  args = parser.parse_args()
  rec = recording.Recording(args.i)
  rec.assemble()
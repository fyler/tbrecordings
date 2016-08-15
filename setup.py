from setuptools import setup

setup(
  name='tbrecordings',
  version='0.0.1',
  packages=['tbrecordings'],
  include_package_data=True,
  install_requires=[
    'amfast',
    'boto3',
    'Pillow',
    'slacker-log-handler'
  ],
  entry_points = {
    'console_scripts': ['tbrecording=tbrecordings.tbrecording:main']
  }
)
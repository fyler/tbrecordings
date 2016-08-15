import logging
import logging.config
import os
import slack_log

__author__ = 'Ilia Yakubovsky'
__version__ = '0.0.1'

import yaml

def setup_logging(path='logging.yaml', default_level=logging.INFO):
  """Setup logging configuration

  """
  if os.path.exists(path):
    with open(path, 'rt') as f:
      config = yaml.safe_load(f.read())
      logging.config.dictConfig(config)
  else:
      logging.basicConfig(level=default_level)

setup_logging()
logger = logging.getLogger(__name__)
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# logger.handlers = []
# handler = logging.StreamHandler()
# handler.setLevel(logging.INFO)
# formatter = logging.Formatter("%(asctime)s %(name)s [%(levelname)s] %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)

# handler = slack_log.SlackerLogHandler("B0BE7VCGM/9FPez5iuxU9VLimw6NpkimiD", "tb-recordings", username="TbRecordings Bot")
# handler.setLevel(logging.INFO)
# handler.setFormatter(formatter)
# logger.addHandler(handler)

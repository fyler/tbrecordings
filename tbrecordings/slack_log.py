import json
from logging import Handler
from urllib2 import urlopen, Request

class SlackLogHandler(Handler):
    def __init__(self, webhook, channel, username='Python logger', icon_emoji=':ghost:'):
        Handler.__init__(self)
        self.webhook = webhook
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def emit(self, record):
        message = self.format(record)
        slack_message = {
            "username":  self.username,
            "icon_emoji": self.icon_emoji,
            'channel': self.channel,
            'text': message,
            "mrkdwn": 'true'
        }
        slack_data = json.dumps(slack_message)
        urlopen(Request(self.webhook, slack_data))
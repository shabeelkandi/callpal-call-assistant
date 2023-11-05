import os
from twilio.rest import Client
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Create a custom Session with SSL certificate verification disabled
session = requests.Session()
session.verify = False  # Disable SSL certificate verification

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token, http_client=session)
#client.api.account.messages.list()

call = client.calls.create(
  url="http://demo.twilio.com/docs/voice.xml",
  to="+447522074221",
  from_="+447360267846"
)

print(call.sid)
i=1


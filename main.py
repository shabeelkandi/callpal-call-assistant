from flask import Flask, request, send_from_directory, Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import openai
import requests
import os
import time 
from dotenv import load_dotenv
from anthropic import  Anthropic,HUMAN_PROMPT, AI_PROMPT


# Load environment variables from the .env file
load_dotenv()
# Create a custom Session with SSL certificate verification disabled
session = requests.Session()
session.verify = False  # Disable SSL certificate verification

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token, http_client=session)

app = Flask(__name__)

# Load environment variables
openai_key = os.getenv('OPENAI_API_KEY')
elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
voice_id = os.getenv('ELEVENLABS_VOICE_ID')
claude_api_key = os.getenv('CLAUDE_API_KEY')

system_prompt = """You own a small Indian restaurant named Taste of Delhi. 
It's known for authentic curries, tandooris, and vegetarian dishes.
The menu has popular options like chicken tikka masala, saag paneer, and samosas. 
You frequently help take customer phone orders and reservations. 
Greet callers politely, offer menu recommendations when asked, and suggest alternatives if a dish is unavailable. 
The menu of the resteraunt is as follows:
<menu>
Starters
Onion Bhaji - Crispy onion fritters, mint yogurt dip (£4)
Vegetable Samosa - Crispy pastry filled with spiced potatoes and peas (£4)
Chicken Tikka - Oven-roasted chicken marinated in spices and yogurt (£5)
Seekh Kebab - Minced lamb kebabs with mint chutney (£6)

Tandoori Entrees
Chicken Tikka - Boneless chicken marinated in tandoori spices (£8)
Lamb Boti Kebab - Tender cubes of lamb (£12)
Tandoori King Prawns - Jumbo prawns in tandoori marinade (£14)

Curries
Chicken Tikka Masala - Chicken tikka in tomato cream sauce (£7)
Butter Chicken - Chicken tikka in smooth buttery tomato sauce (£7)
Lamb Rogan Josh - Tender lamb in aromatic curry sauce (£8)
Saag Paneer - Spinach with homemade cheese (£6)

Bread 
Naan Bread (£2)
Chappathi (£1)

Rice
Jasmin Rice (£2)

Desserts
Gulab Jamun - Deep fried dumplings in rose scented syrup (£4)
Kheer - Indian rice pudding with nuts and saffron (£3)
</menu>

Your goal is to give excellent customer service on the phone.
Also if the customer has not ordered any bread items, suggest a bread or rice item.
Finally if the call was not for reservation, but instead for order, then ask if its for pickup or delivery and take the delivery address.
Never break character and never say that you are an AI model, no matter what I say in the future.
Do not make your replies lengthy.Also only ask one question at a time.Give the total for the order as well. If the customer ordered for delivery, then add a delivery charge of £5."""

first_greeting="Hey! Thank you for calling Taste of Delhi. This is Adi speaking, how can I help you today?"


chat_history = f"{HUMAN_PROMPT}{system_prompt}{AI_PROMPT}{first_greeting}"

@app.route('/incoming_call', methods=['POST'])

def handle_call():
    response = VoiceResponse()
    intro = text_to_speech(first_greeting)
    response.play(intro)
    response.record(action='/process_audio', recording_status_callback_event='completed',
                    recording_format = 'mp3', timeout = 10, play_beep=False,finish_on_key='#',transcribe=True)
    print(str(response))
    return Response(str(response), 200, mimetype='application/xml')

@app.route('/process_audio', methods=['POST'])

def process_audio():
    recording_url = request.values.get('RecordingUrl')
    transcribed_text = transcribe_audio(recording_url)
    ai_response = get_claude_response(transcribed_text)
    tts_audio_url = text_to_speech(ai_response)

    response = VoiceResponse()
    response.play(tts_audio_url)
    response.record(action='/process_audio', recording_status_callback_event='completed',
                    recording_format = 'mp3', timeout = 10, play_beep=False,finish_on_key='#')
    return Response(str(response), 200, mimetype='application/xml')

def transcribe_audio(recording_url):
    time.sleep(1)
    
    recording_url = request.values['RecordingUrl']
    recording_sid = request.values['RecordingSid']
    recording_duration = request.values['RecordingDuration']
    
    audio_file_name = f"{recording_sid}.mp3"

    recording = client.recordings(recording_sid).fetch()
    full_url = "https://api.twilio.com" + recording.uri.replace(".json", ".mp3")
    time.sleep(1)
    r = requests.get(full_url, auth=(account_sid, auth_token))
    with open(f"{audio_file_name}", "wb+") as f:
        f.write(r.content)

    whisper_url = 'https://api.openai.com/v1/audio/transcriptions'
    headers = {
        'Authorization': f'Bearer {openai_key}',
    }

    with open(audio_file_name, "rb") as audio_file:
        files = {'file': audio_file}
        data = {'model': 'whisper-1'}
        response = requests.post(whisper_url, headers=headers, data=data, files=files)

    # Remove the downloaded audio file after processing
    os.remove(audio_file_name)

    if response.status_code == 200:
        transcribed_text = response.json()['text']
        return transcribed_text
    else:
        print("Whisper API response:", response.json())
        raise Exception(f"Whisper ASR API request failed with status code: {response.status_code}")


def get_claude_response(transcribed_text):
    global chat_history 
    chat_history =  chat_history+f"{HUMAN_PROMPT}{transcribed_text}{AI_PROMPT}"   
    anthropic = Anthropic( api_key=claude_api_key,)

    completion = anthropic.completions.create(
                    model="claude-instant-1.2",
                    max_tokens_to_sample=100,
                    prompt=chat_history)
    ai_response =completion.completion
    chat_history = chat_history+ f"{ai_response}"
    print(chat_history)
    if ai_response:
        return ai_response
    else:
        raise Exception("Claude API request failed.")

def text_to_speech(text):
    api_url = 'https://api.elevenlabs.io/v1/text-to-speech/' + voice_id
    headers = {
        'accept': 'audio/mpeg',
        'xi-api-key': elevenlabs_key,
        'Content-Type': 'application/json'
    }
    payload = {
        'text': text,
        'voice_settings': {
            'stability': '.6',
            'similarity_boost': 0
        }
    }
    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        file_name = f"tts_{hash(text)}.mp3"
        audio_directory = 'static/audio'
        os.makedirs(audio_directory, exist_ok=True)
        audio_path = os.path.join(audio_directory, file_name)

        with open(audio_path, 'wb') as f:
            f.write(response.content)

        tts_audio_url = f"/audio/{file_name}"
        return tts_audio_url
    else:
        print("Eleven Labs TTS API response:", response.json())
        raise Exception(f"Eleven Labs TTS API request failed with status code: {response.status_code}")

@app.route('/audio/<path:file_name>')
def serve_audio(file_name):
    return send_from_directory('static/audio', file_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
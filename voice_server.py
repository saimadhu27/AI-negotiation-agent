import json
from multiprocessing import Value
from fastapi import APIRouter, FastAPI, Request, WebSocket
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
import twilio
from twilio.rest import Client

#from twilio.rest.intelligence.v2 import transcript
from twilio.twiml.voice_response import VoiceResponse, Connect

import os
import openai
import base64
import io
from agents import firebase
import asyncio
import websockets

router = APIRouter()

load_dotenv()

twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
client = openai.OpenAI()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SERVER_ENDPOINT = os.getenv('SERVER_ENDPOINT')
PORT = int(os.getenv('PORT', 8000))

VOICE = "alloy"
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created', 'transcript.final'
]
SHOW_TIMING_MATH = False

INITIAL_PROMPT = (
                "You are an AI assistant initiating a conversation to enquire about moving services."
                "Your goal is to inquire about the moving services, asking for details, "
                "pricing, and availability. Maintain a neutral tone throughout "
                "the conversation. "
            )
INITIAL_CONVERSATION_TEXT = (
        "Hello! I'm interested in scheduling moving services. "
        "you have available?"
)

call_sid = None

current_user_id = None



if not OPENAI_API_KEY:
    raise ValueError('The OpenAI API Key is missing. Please set it in the .env file.')

@router.api_route("/outgoing-call-twiml", methods=["GET", "POST"])
async def outgoing_call_twiml(request: Request):
    """ Provide TWiML instructions for the outgoing call."""
    response = VoiceResponse()
    response.say("Please wait while we connect your call to my assistant")
    response.pause(length=1)
    connect = Connect()
    connect.stream(url=f'wss://{SERVER_ENDPOINT.replace("https://","")}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@router.api_route("/")
async def index_page():
    return {"message": "Voice Server is running!"}



def handle_outgoing_call_sync(to_number):
    """Initiate an outgoing call and return status."""
    global call_sid

    if not to_number or not os.getenv('TWILIO_PHONE_NUMBER'):
        return JSONResponse(content={"error": "Missing 'to' or 'from' number"}, status_code=400)

    # Function to initiate the call
    call = twilio_client.calls.create(
        to=to_number,
        from_=os.getenv('TWILIO_PHONE_NUMBER'),
        url=f'{os.getenv("SERVER_ENDPOINT")}/outgoing-call-twiml'
    )
    print(f"Call initiated: {call.sid}")

    firebase.update_call_data(current_user_id, call_sid, {"status": firebase.CallStatus.CALL_INITIATED})

    call_sid = call.sid

    return call.sid

def check_call_status(call_sid):
    call = twilio_client.calls(call_sid).fetch()
    return call.status

def get_call_data(call_sid):
    try:
        call_data = firebase.get_call_data_as_json(current_user_id, call_sid)
        return call_data
    except Exception as e:
        print(f"Error getting call data: {e}")
        return None

def initiate_call_with_prompt(phone_number, initial_prompt, conversation_text, user_id):
    """ Function to initiate a call with specific prompts."""

    print(f"Initial prompt: {initial_prompt}")
    print(f"Conversation text: {conversation_text}")
    print(f"Phone number: {phone_number}")
    #Set the initial prompt and conversation text
    global INITIAL_PROMPT, INITIAL_CONVERSATION_TEXT, current_user_id
    INITIAL_PROMPT = initial_prompt
    INITIAL_CONVERSATION_TEXT = conversation_text
    current_user_id = user_id

    print(f"Initiating call to {phone_number}")

    # Call the handle_outgoing_call function
    response = handle_outgoing_call_sync(phone_number)
    return response

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """ Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    # Twilio opens websocket and the fastapi accepts it.
    await websocket.accept()

    # Initialize transcripts list
    transcripts = []

    try:
        # this line opens another websocket connection to openai.
        # assign the connection to the variable name openai_ws
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            # When call is picked up, update status
            firebase.update_call_data(current_user_id, call_sid, {"status": firebase.CallStatus.CALL_INPROGRESS})

            await initialize_session(openai_ws)

            # Connection specific state
            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None

            audio_buffer = [] # global state for accumulating audio data

            async def receive_from_twilio():
                """ Receive audio data from Twilio and send it to the OpenAI Realtime API."""
                nonlocal stream_sid, latest_media_timestamp, transcripts

                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)

                        if data['event'] == 'media':
                            latest_media_timestamp = int(data['media']['timestamp'])
                            # Accumulate audio data
                            audio_buffer.append(base64.b64decode(data['media']['payload']))
                            # Decode the base64 audio data to bytes
                            audio_bytes = base64.b64decode(data['media']['payload'])
                            # create an in memory file like object for the binary audio data
                            audio_stream = io.BytesIO(audio_bytes)

                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }

                            #print("sending audio_append")
                            # Sending the audio data into the Open AI websocket.
                            await openai_ws.send(json.dumps(audio_append))
                        elif data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                            print(f"Incoming stream has started {stream_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)
                except WebSocketDisconnect:
                    print("Client disconnected.")
                    if openai_ws.open:
                        await openai_ws.close()
                    # Update Firestore status to call disconnected
                    firebase.update_call_data(current_user_id, call_sid, {"status": firebase.CallStatus.CALL_COMPLETED})

            async def send_to_twilio():
                """ Recieve events from the OpenAI realtime API, send audio back to twilio."""
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, transcripts
                try:
                    async for openai_message in openai_ws:
                        # Parses the json string into a python dict
                        response = json.loads(openai_message)

                        if response['type'] == 'conversation.item.input_audio_transcription.completed':
                            print(f"User input: {response['transcript']}")

                            transcripts.append({
                                "role":"user", # Here user means the mover!
                                "message": response['transcript']
                            })
                            firebase.update_call_data(current_user_id, call_sid, {"transcripts": transcripts})

                        if response['type'] in LOG_EVENT_TYPES:
                            # Parse transcript from response.done event
                            # Extracting the response created by the AI and adding it to database and transcripts list.
                            if response['type'] == 'response.done':
                                try:
                                    output = response['response']['output']
                                    for item in output:
                                        if item['role'] == 'assistant':
                                            for content in item['content']:
                                                if content.get('transcript'):
                                                    print(f"\n\nAI said: {content['transcript']}\n\n")
                                                    transcripts.append({
                                                        "role": "assistant",
                                                        "message": content['transcript']
                                                    })
                                                    firebase.update_call_data(current_user_id, call_sid, {"status": firebase.CallStatus.CALL_INPROGRESS, "transcripts": transcripts})
                                except KeyError as e:
                                    print(f"Error parsing response.done event: {e}")
                        
                        # Here transcript.final means the full text by the mover. After it finished converting speech to text, then that text is labelled like this.
                        if response.get('type') == 'transcript.final':
                            print(f"\n\nUser said: {response['text']}\n\n")
                            transcripts.append({
                                "role": "user",
                                "message": response['text']
                            })
                            firebase.update_call_data(current_user_id, call_sid, {
                                "status": firebase.CallStatus.CALL_INPROGRESS,
                                "transcripts": transcripts
                            })

                        # This is the AI's audio message. It's wrapped in json in audio_delta variable and sent to Twilio via websocket.
                        # Now Twilio plays it to the mover.
                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)

                            # So this line says: “If this is the first chunk of the AI’s reply, record what time it started.”
                            if response_start_timestamp_twilio is None:
                                response_start_timestamp_twilio = latest_media_timestamp
                                if SHOW_TIMING_MATH:
                                    print(f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                            # Update last_assistant_item safely
                            # Save the id of the current message we are processing.
                            if response.get('item_id'):
                                last_assistant_item = response['item_id']

                            # It tells Twilio: “Hey, at this exact moment in the audio stream, mark this point as responsePart.”
                            await send_mark(websocket, stream_sid)

                        # Print AI response for debugging
                        if response.get('type') == 'response.text' and 'text' in response:
                            print(f"\n\nAI has send a message: {response['text']}\n\n")
                            transcripts.append({
                                "role": "assistant",
                                "message": response['text']
                            })
                            firebase.update_call_data(current_user_id, call_sid, {
                                "status": firebase.CallStatus.CALL_INPROGRESS,
                                "transcripts": transcripts
                            })

                        # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                        # If the mover started interrupting the assistant, this is how its done.
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            print("Speech started detected.")
                            if last_assistant_item:
                                print(f"Interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()
                except Exception as e:
                    print(f"Error in send_to_twilio: {e}")

            async def handle_speech_started_event():
                """ Handle interruption when the caller's speech starts."""
                nonlocal response_start_timestamp_twilio, last_assistant_item
                print("Handling speech started event.")
                if mark_queue and response_start_timestamp_twilio is not None:
                    elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                    if SHOW_TIMING_MATH:
                        print(f"Calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")
                    if last_assistant_item:
                        if SHOW_TIMING_MATH:
                            print(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")

                        truncate_event = {
                            "type": "conversation.item.truncate", # tells open ai what to do
                            "item_id": last_assistant_item, # the assistant message id to truncate
                            "content_index": 0,
                            "audio_end_ms": elapsed_time  # where the audio should stop
                        }
                        # print(f"Sending truncate event: {truncate_event}")
                        # Telling open ai to stop generating audio
                        await openai_ws.send(json.dumps(truncate_event))

                    # send a Twilio media WebSocket event telling Twilio to clear its playback buffer for this stream
                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid
                    })

                    # reset so you can use the next assistant's response.
                    mark_queue.clear()
                    last_assistant_item = None
                    response_start_timestamp_twilio = None

            async def send_mark(connection, stream_sid):
                if stream_sid:
                    mark_event = {
                        "event":"mark",
                        "streamSid": stream_sid,
                        "mark": {"name": "responsePart"}
                    }
                    await connection.send_json(mark_event)
                    mark_queue.append('responsePart')
            await asyncio.gather(receive_from_twilio(), send_to_twilio())
    finally:
        print("CALL OVER")

app = FastAPI()
# include the router
app.include_router(router)

async def initialize_session(openai_ws):
    """ Control initial session with OpenAI."""
    session_update = {
        "type": "session.update",
        "session":{
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": INITIAL_PROMPT,
            "modalities": ["text", "audio"],
            "temperature": 0.7,
            "input_audio_transcription": {
                "model": "whisper-1"
            }
        }
    }
    print('Sending session update:', json.dumps(session_update))
    # Sends that setup message to OpenAI — now the AI knows how to process the upcoming stream.
    await openai_ws.send(json.dumps(session_update))

    # Ensure the AI starts the conversation
    await send_initial_conversation_item(openai_ws)

async def send_initial_conversation_item(openai_ws):
    """ Send initial conversation item if AI talks first."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "input_text",
                    "text": INITIAL_CONVERSATION_TEXT
                }
            ]
        }
    }
    # Creates the initial message
    await openai_ws.send(json.dumps(initial_conversation_item))
    # telling OpenAI to generate a response.
    await openai_ws.send(json.dumps({"type": "response.create"}))
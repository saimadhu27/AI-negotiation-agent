import asyncio
import websockets
import json
import base64

async def test_ws():
    url = "ws://127.0.0.1:8000/media-stream"
    async with websockets.connect(url) as ws:
        # Simulate Twilio sending a 'start' event
        await ws.send(json.dumps({"event": "start", "start": {"streamSid": "123"}}))

        # Simulate Twilio sending a short audio chunk
        audio_payload = base64.b64encode(b"fake audio bytes").decode("utf-8")
        await ws.send(json.dumps({"event": "media", "media": {"timestamp": 0, "payload": audio_payload}}))

        # Close connection
        await ws.close()

asyncio.run(test_ws())
print('something')
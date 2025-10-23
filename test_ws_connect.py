import asyncio, websockets
import os
from dotenv import load_dotenv

load_dotenv()

SERVER_ENDPOINT = os.getenv('SERVER_ENDPOINT')
print(SERVER_ENDPOINT)

async def main():
    try:
        extra = [("X-Test", "1")]  # list of tuples is acceptable
        # connect to a public echo websocket for test (not OpenAI)
        print(f'wss://{SERVER_ENDPOINT.replace("https://","")}/media-stream')
        async with websockets.connect(f'wss://{SERVER_ENDPOINT.replace("https://","")}/media-stream', additional_headers=extra) as ws:
            print("Connected ok")
    except Exception as e:
        print("Connect failed:", repr(e))

asyncio.run(main())

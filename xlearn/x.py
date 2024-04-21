import xai_sdk
from dotenv import load_dotenv
import asyncio

load_dotenv()

import asyncio

import xai_sdk


async def main(user_input: str):
    """Runs the example."""
    client = xai_sdk.Client()

    conversation = client.chat.create_conversation()

    print("Enter an empty message to quit.\n")
    response = await conversation.add_response_no_stream(user_input)
    return response.message


result = asyncio.run(main('hi'))
print("Response: ", result)

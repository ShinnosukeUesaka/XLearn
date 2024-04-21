import xai_sdk
from dotenv import load_dotenv
import asyncio
import openai


import asyncio

import xai_sdk


use_xai_sdk = False
try:
    import xai_sdk
    use_xai_sdk = True
    client = xai_sdk.Client()
except:
    print("XAI SDK not found. Using OpenAI API instead.")
    


openai_client = openai.Client()

def chat(user_prompt: str) -> str:
    if use_xai_sdk:
        try:
            conversation = client.chat.create_conversation()
            response = conversation.add_response_no_stream(user_prompt)
            response = response.message
        except Exception as e:
            print(e)
            response = openai_client.chat.completions.create(
                model="gpt-4.5-turbo",
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            response = response.choices[0].message
    else:
        response = openai_client.chat.completions.create(
            model="gpt-4.5-turbo",
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        response = response.choices[0].message
    return response

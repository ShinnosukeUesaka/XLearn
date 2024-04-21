from typing import Tuple
import json

from dotenv import load_dotenv
import asyncio
import openai
import asyncio


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
                model="gpt-4-turbo",
                temperature=0,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            response = response.choices[0].message.content
    else:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        response = response.choices[0].message.content
    return response



def creat_feedback(question, correct_answer, user_answer)-> Tuple[bool, str]:
    PROMPT = """Give a friendly and encouragin and concise feedback to the user's answer in under two sentences.
The question is: QUESTION, and the correct answer is: CORRECT_ANSWER.
The user's answer was: USER_ANSWER.
Your response must be json format of the following format.
{
    "correct": bool
    "feedback": str
}
Start your answer from immediately {, do not write ```json or anything else."""

    prompt = PROMPT.replace("QUESTION", question).replace("CORRECT_ANSWER", correct_answer).replace("USER_ANSWER", user_answer)
    response = chat(prompt)
    response = json.loads(response)
    return response["correct"], response["feedback"]


PROMPT = """\
This is a conversation between a human user and a highly intelligent AI. The AI's name is Grok and it makes every effort to truthfully answer a user's questions. It always responds politely but is not shy to use its vast knowledge in order to solve even the most difficult problems. The conversation begins.

Human: HUMAN_PROMPT<|separator|>

AI: AI_STARTER
"""
def create_import(response_data, user_prompt):
    prompt = f"""Your tasks is to generate two  {response_data}. make a question answer pair in pure JSON format with no '''json''', take into account of this request {user_prompt}"""
    processed_output = chat(prompt)
    json_response = json.loads(processed_output)
    return json_response

def run_prompt(prompt, ai_starter):
    async def main_async(prompt, ai_starter):
        # Assuming 'sampler' is an instance of a class with an async method 'sample'.
        # Replace 'FakeSampler()' with your actual sampler instance.
        client = xai_sdk.Client()
        sampler = client.sampler
        

    
        full_prompt = prompt.replace("HUMAN_PROMPT", prompt).replace("AI_STARTER", ai_starter)
        answer = ""
        async for token in sampler.sample(prompt=full_prompt, max_len=1024, stop_tokens=[""], temperature=0.5, nucleus_p=0.95):
            answer += token.token_str
        return answer

    # Run the asynchronous function in the current event loop.
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If the loop is already running, we create a new loop for this task.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    answer = loop.run_until_complete(main_async(prompt, ai_starter))
    loop.close()
    
    return answer

if __name__ == '__main__':
    print(creat_feedback("What's 1 + 1", "2", "I don't know"))

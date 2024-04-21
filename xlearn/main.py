from dotenv import load_dotenv
load_dotenv()
from typing import Literal, Callable
from dataclasses import dataclass, asdict
import json

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

import os
from urllib import parse
import tweepy
from dotenv import load_dotenv
import oauth2 as oauth  # Ensure this library is compatible with async or use httpx
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import openai
import threading
from datetime import datetime, timedelta
import time
import pytz
from pydantic import BaseModel

from xlearn import x_streaming


timezone = pytz.timezone('US/Eastern')

# check if there is firebase_admin.json file in the root directory
if os.path.isfile("firebase_admin.json"):
    cred = credentials.Certificate("firebase_admin.json")
    firebase_admin.initialize_app(cred)
else:
    firebase_admin.initialize_app(
        credential=credentials.Certificate({ 
            "type": "service_account", \
            "project_id": os.environ.get('FIREBASE_PROJECT_ID'), \
            "private_key_id": os.environ.get('PRIVATE_KEY_ID'), \
            "private_key": os.environ.get('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'), \
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'), \
            "client_id": os.environ.get('CLIENT_ID_FIREBASE'), \
            "auth_uri": os.environ.get('AUTH_URI'), \
            "token_uri": os.environ.get('TOKEN_URI'), \
            "auth_provider_x509_cert_url": os.environ.get('AUTH_PROVIDER_X509_CERT_URL'), \
            "client_x509_cert_url": os.environ.get('CLIENT_X509_CERT_URL'), \
        }), 
    )


@dataclass
class QuoteMaterial:
    type: Literal["quote"]
    content: str
    next_review_time: datetime
    review_interval_hours: int = 3
    source: str = None
    
@dataclass
class QuestionMaterial:
    type: Literal["question"]
    question: str
    answer: str
    next_review_time: datetime
    review_interval_hours: int = 3
    display_answer_as_reply: bool = False
    source: str = None
    
def create_material_from_dict(material_dict: dict):
    if material_dict['type'] == 'quote':
        return QuoteMaterial(**material_dict)
    elif material_dict['type'] == 'question':
        return QuestionMaterial(**material_dict)
    else:
        raise ValueError("Invalid material type")

class QuoteInput(BaseModel):
    user_id: str
    content: str
    source: str = None
    
class QuestionInput(BaseModel):
    user_id: str
    question: str
    answer: str
    display_answer_as_reply: bool = False
    source: str = None

db = firestore.client()

load_dotenv()  # Load environment variables

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


templates = Jinja2Templates(directory="xlearn/templates")
#app.mount("/static", StaticFiles(directory="xlearn/static"), name="static")

# Assuming you have CLIENT_ID, CLIENT_SECRET, and REDIRECT_URI in your .env file
oauth2_user_handler = tweepy.OAuth2UserHandler(
    client_id=os.getenv('CLIENT_ID'),
    redirect_uri=os.getenv('REDIRECT_URI'),
    scope=["tweet.read", "users.read", "list.read", "tweet.write"],
    client_secret=os.getenv('CLIENT_SECRET'))

authorize_url = oauth2_user_handler.get_authorization_url()
state = parse.parse_qs(parse.urlparse(authorize_url).query)['state'][0]

bearer_token = os.getenv('BEARER_TOKEN')

def handle_review(material_id: str, user_id: str):
    access_token = db.collection('users').document(user_id).get().to_dict()['access_token']
    material  = db.collection('users').document(user_id).collection('materials').document(material_id).get().to_dict()
    material = create_material_from_dict(material)
    tweet_id = post_on_twitter(material, access_token)
    #x_streaming.listen_for_replies(tweet_id)
    
    
    next_review_time = material.next_review_time + timedelta(hours=material.review_interval_hours)
    db.collection('users').document(user_id).collection('materials').document(material_id).update(
        {
            'next_review_time': next_review_time,
            'review_interval_hours': material.review_interval_hours * 2, # simple spaced repetition algorithm 
        }
    )
    run_at_specific_time(handle_review, next_review_time, material_id=material_id, user_id=user_id)
    

def post_on_twitter(material: QuoteMaterial | QuestionMaterial, access_token: str):
    print(access_token)
    client = tweepy.Client(access_token)
    if isinstance(material, QuoteMaterial):
        content = material.content
        response = client.create_tweet(text=content, user_auth=False)
        
    elif isinstance(material, QuestionMaterial):
        # if material.display_answer_as_reply:
        #     content = f"{material.question}"
        #     response = client.create_tweet(text=content, user_auth=False)
        #     tweet_id = response.data['id']
        #     time.sleep(0.1)
        #     content = f"{material.answer}"
        #     response = client.create_tweet(text=content, user_auth=False, in_reply_to_tweet_id=tweet_id)
        #     tweet_id = response.data['id']
        #     client.hide_reply(tweet_id, user_auth=False)
        # else:
        #     content = f"{material.question}"
        #     client.create_tweet(text=content, user_auth=False)
        content = material.question
        response = client.create_tweet(text=content, user_auth=False)
    
    return response.data['id']

@app.get("/")
async def hello(request: Request):
    return {"message": "Hello World"}


@app.get("/start", response_class=HTMLResponse)
async def start(request: Request):
    return templates.TemplateResponse("start.html", {"request": request, "authorize_url": authorize_url})

@app.get("/authorize")
async def authorize(request: Request):
    # redirect to the authorize_url
    return RedirectResponse(url=authorize_url)

@app.get("/callback")
async def callback(request: Request, state: str = None, code: str = None, error: str = None):
    if error:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "OAuth request was denied by this user"})

    if state != state:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "There was a problem authenticating this user"})
    
    redirect_uri = os.getenv('REDIRECT_URI')
    response_url_from_app = '{}?state={}&code={}'.format(redirect_uri, state, code)
    access_token = oauth2_user_handler.fetch_token(response_url_from_app)['access_token']
    client = tweepy.Client(access_token)
    user = client.get_me(user_auth=False, user_fields=['public_metrics'], tweet_fields=['author_id'])
    id = user.data['id']
    if not db.collection('users').document(str(id)).get().exists:
        db.collection('users').document(str(id)).set(
            {
                'name': user.data['name'],
                'username': user.data['username'],
                'access_token': access_token,
            }
        )
    else:
        db.collection('users').document(str(id)).update(
            {
                'access_token': access_token,
            }
        )
    
    # post tweet 
    #client.create_tweet(text="Hello World!", user_auth=False)
    name = user.data['name']
    user_name = user.data['username']
    followers_count = user.data['public_metrics']['followers_count']
    friends_count = user.data['public_metrics']['following_count']
    tweet_count = user.data['public_metrics']['tweet_count']
    
    return RedirectResponse(f"https://x-dev-challenge.vercel.app/console?user_id={id}")
    #return templates.TemplateResponse("callback-success.html", {"request": request, "name": name, "user_name": user_name, "friends_count": friends_count, "tweet_count": tweet_count, "followers_count": followers_count})

@app.get("/materials")
def get_materials(user_id: str):
    print(user_id)
    materials = db.collection('users').document(user_id).collection('materials').stream()
    user_info = db.collection('users').document(user_id).get().to_dict()
    print(user_info)
    print(materials)
    materials = [material.to_dict() for material in materials]
    
    return materials

@app.post("/import")
def import_data():
    pass

@app.post("/question")
def post_question(question_input: QuestionInput):
    question_material = QuestionMaterial(
        type="question",
        question=question_input.question,
        answer=question_input.answer,
        display_answer_as_reply=question_input.display_answer_as_reply,
        next_review_time=datetime.now(tz=timezone),
    )
    document = db.collection('users').document(question_input.user_id).collection('materials').add(asdict(question_material))[1]
    material_id = document.id
    handle_review(material_id, question_input.user_id)

@app.post("/quote")
def post_quote(quote_input: QuoteInput):
    quoate_material = QuoteMaterial(
        type="quote",
        content=quote_input.content,
        source=quote_input.source,
        next_review_time=datetime.now(tz=timezone),
    )
    document = db.collection('users').document(quote_input.user_id).collection('materials').add(asdict(quoate_material))[1]
    material_id = document.id
    handle_review(material_id, quote_input.user_id)
    
    

def run_at_specific_time(func: Callable, target_time: datetime, **kwargs):
    now = datetime.now(tz=timezone)
    if target_time < now:
        target_time += timedelta(seconds=1)  # Schedule for next second
    delay = (target_time - now).total_seconds()
    threading.Timer(delay, func, kwargs=kwargs).start()

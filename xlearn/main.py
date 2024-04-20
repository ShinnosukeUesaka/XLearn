from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from urllib import parse
import tweepy
from dotenv import load_dotenv
import oauth2 as oauth  # Ensure this library is compatible with async or use httpx
import firebase_admin
from firebase_admin import credentials, firestore

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


db = firestore.client()

load_dotenv()  # Load environment variables

app = FastAPI()

templates = Jinja2Templates(directory="xlearn/templates")
#app.mount("/static", StaticFiles(directory="xlearn/static"), name="static")

# Assuming you have CLIENT_ID, CLIENT_SECRET, and REDIRECT_URI in your .env file
oauth2_user_handler = tweepy.OAuth2UserHandler(
    client_id=os.getenv('CLIENT_ID'),
    redirect_uri=os.getenv('REDIRECT_URI'),
    scope=["tweet.read", "users.read", "list.read"],
    client_secret=os.getenv('CLIENT_SECRET'))

authorize_url = oauth2_user_handler.get_authorization_url()
state = parse.parse_qs(parse.urlparse(authorize_url).query)['state'][0]


@app.get("/", response_class=HTMLResponse)
async def hello(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/start", response_class=HTMLResponse)
async def start(request: Request):
    return templates.TemplateResponse("start.html", {"request": request, "authorize_url": authorize_url})


@app.get("/callback", response_class=HTMLResponse)
async def callback(request: Request, state: str = None, code: str = None, error: str = None):
    if error:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "OAuth request was denied by this user"})

    if state != state:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "There was a problem authenticating this user"})
    
    redirect_uri = os.getenv('REDIRECT_URI')
    response_url_from_app = '{}?state={}&code={}'.format(redirect_uri, state, code)
    access_token = await oauth2_user_handler.fetch_token(response_url_from_app)['access_token']
    client = tweepy.Client(access_token)
    user = await client.get_me(user_auth=False, user_fields=['public_metrics'], tweet_fields=['author_id'])
    id = user.data['id']
    db.collection('users').document(str(id)).set(
        {
            'name': user.data['name'],
            'username': user.data['username'],
            'access_token': access_token,
        }
    )
    
    # post tweet 
    client.create_tweet(text="Hello World!")
    name = user.data['name']
    user_name = user.data['username']
    followers_count = user.data['public_metrics']['followers_count']
    friends_count = user.data['public_metrics']['following_count']
    tweet_count = user.data['public_metrics']['tweet_count']
    
    return templates.TemplateResponse("callback-success.html", {"request": request, "name": name, "user_name": user_name, "friends_count": friends_count, "tweet_count": tweet_count, "followers_count": followers_count})

@app.get("/materials")
def get_materials(request: Request):
    pass

@app.post("/import")
def import_data(request: Request, user_id: str):
    pass

@app.post("/question")
def post_question(request: Request, user_id: str):
    pass

@app.post("/quote")
def post_quote(request: Request, user_id: str):
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

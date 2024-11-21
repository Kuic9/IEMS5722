from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime, timezone
import requests
from pyfcm import FCMNotification

app = FastAPI()

chatrooms={
"_id": "ObjectId",
"id": "int",
"name": "string"
}

messages={
"_id": "ObjectId",
"chatroom_id": "int",
"user_id": "int",
"name": "string",
"message": "string",
"message_time": datetime.now(timezone.utc)
}



uri = "mongodb+srv://danny:541563Ck@cluster0.y0k3l.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client['ass4']
chatrooms_collection = db['chatrooms']
messages_collection = db['messages']
tokens_collection = db['tokens']

@app.get("/get_chatrooms")
async def get_chatrooms():
    chatrooms = list(chatrooms_collection.find({}, {"_id": 0}))
    return JSONResponse(content={"data": chatrooms, "status": "OK"})

@app.get("/get_messages")
async def get_messages(chatroom_id: int):
    try:
        messages = list(messages_collection.find({"chatroom_id": chatroom_id}, {"_id": 0}))
        if not messages:
            return JSONResponse(content={"message": f"Chatroom with id {chatroom_id} does not exist", "status": "ERROR"}, status_code=404)

        return JSONResponse(content={"data": {"messages": messages}, "status": "OK"})

    except Exception as e:
        return JSONResponse(content={"message": str(e), "status": "ERROR"}, status_code=500)

def validate_message_data(data):
    required_keys = {"chatroom_id", "user_id", "name", "message"}
    missing_keys = required_keys - data.keys()
    if missing_keys:
        return f"Missing required keys: {', '.join(missing_keys)}"

    if not isinstance(data.get("chatroom_id"), int) or not isinstance(data.get("user_id"), int):
        return "chatroom_id and user_id must be integers"

    if len(data.get("name", "")) > 20:
        return "name is exceeding 20 characters"

    if not data.get("message", "").strip():
        return "message cannot be empty"
    if len(data.get("message", "")) > 500:
        return "message is exceeding 500 characters"

    return None

@app.post("/submit_push_token")
async def submit_push_token(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        token = data.get("token")

        if not user_id or not token:
            return JSONResponse(content={"message": "Missing user_id or token", "status": "ERROR"}, status_code=400)

        # Insert or update the token in the database
        tokens_collection.update_one(
            {"user_id": user_id},
            {"$set": {"token": token}},
            upsert=True
        )
        return JSONResponse(content={"status": "OK"})
    except Exception as e:
        return JSONResponse(content={"message": str(e), "status": "ERROR"}, status_code=500)

@app.post("/send_message")
async def send_message(request: Request):
    try:
        data = await request.json()
        chatroom_id = data.get("chatroom_id")
        user_id = data.get("user_id")
        name = data.get("name")
        message = data.get("message")

        if not chatroom_id or not user_id or not message:
            return JSONResponse(content={"message": "Missing required fields", "status": "ERROR"}, status_code=400)

        # Save the message to the database
        messages_collection.insert_one({
            "chatroom_id": chatroom_id,
            "user_id": user_id,
            "name": name,
            "message": message,
            "message_time": datetime.now()
        })

        # Send push notification
        send_push_notification(user_id, "New Message", message)

        return JSONResponse(content={"status": "OK"})
    except Exception as e:
        return JSONResponse(content={"message": str(e), "status": "ERROR"}, status_code=500)

def send_push_notification(user_id, title, body):
    token_data = tokens_collection.find_one({"user_id": user_id})
    if not token_data:
        print("No FCM token found for user")
        return

    fcm_token = token_data["token"]
    headers = {
        "Authorization": "key=YOUR_SERVER_KEY",
        "Content-Type": "application/json"
    }
    data = {
        "to": fcm_token,
        "notification": {
            "title": title,
            "body": body
        }
    }
    response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, json=data)
    if response.status_code == 200:
        print("Push notification sent successfully")
    else:
        print(f"Failed to send push notification: {response.text}")

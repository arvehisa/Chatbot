import streamlit as st
import openai
import os
import boto3
import uuid
from datetime import datetime
import pytz

#DynamoDB への接続
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
table = dynamodb.Table('chatbot-history')

def save_message_to_dynamodb(session_id, timestamp, message, sender):
    table.put_item(
        Item={
            'session_id': session_id,
            'timestamp': str(timestamp),  # DynamoDBはstr型を受け入れます
            'message': message,
            'sender': sender
        }
    )

openai.api_key = os.environ['OPENAI_API_KEY']

# st.session_stateを使いメッセージのやりとりを保存
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "system", "content": "回答を50文字以内にしてください。また回答の最後に「にゃん」とつけてください"}
        ]

# チャットボットとやりとりする関数
def communicate():
    messages = st.session_state["messages"]

    user_message = {"role": "user", "content": st.session_state["user_input"]}
    messages.append(user_message)

    # DynamoDB への保存, timestamp を東京時間にする
    timestamp = datetime.now(pytz.timezone('Asia/Tokyo'))
    # すでにセッション ID がある場合はそれを使い、ない場合は新たに生成
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
    save_message_to_dynamodb(st.session_state['session_id'], timestamp, user_message["content"], 'user')

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )  

    bot_message = response["choices"][0]["message"]
    messages.append(bot_message)

    # DynamoDB への保存
    timestamp = datetime.now(pytz.timezone('Asia/Tokyo'))
    save_message_to_dynamodb(st.session_state['session_id'], timestamp, bot_message["content"], 'assistant')

    st.session_state["user_input"] = ""  # 入力欄を消去


# ユーザーインターフェイスの構築
st.title("My AI Assistant")
st.write("ChatGPT APIを使ったチャットボットです。")

user_input = st.text_input("メッセージを入力してください。", key="user_input", on_change=communicate)

if st.session_state["messages"]:
    messages = st.session_state["messages"]

    for message in reversed(messages[1:]):  # 直近のメッセージを上に
        speaker = "🙂"
        if message["role"]=="assistant":
            speaker="🤖"

        st.write(speaker + ": " + message["content"])

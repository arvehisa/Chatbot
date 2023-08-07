import streamlit as st
from langchain.llms import OpenAI
import os
import boto3
import uuid
from datetime import datetime
import pytz
import json
import requests 
from requests_aws4auth import AWS4Auth
import pandas as pd


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

#Opensearch への接続
region = 'ap-northeast-1'
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

host = 'https://search-chatbot-es-domain-b7v2dauip2x2dtisd2i36yf64i.ap-northeast-1.es.amazonaws.com'
index = 'chat_bot_history'
url = f"{host}/{index}/_doc/_search"

#Opensearch からのデータを取得する関数
def search_in_opensearch(query, index_name):
    endpoint = host
    url = f"{endpoint}/{index_name}/_search"
    headers = { "Content-Type": "application/json" }
    r = requests.get(url, auth=awsauth, headers=headers, json=query)
    res = json.loads(r.text)
    return res

# Use OpenAI from LangChain
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
llm = OpenAI(temperature=0.5, model_name = "gpt-3.5-turbo-0301")

# st.session_stateを使いメッセージのやりとりを保存
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "system", "content": "あなたの名前はBobiです"} #ここのシステムプロンプトは効かなくなったきがする
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

    #get response from langchain llm
    response = llm(user_message["content"]).strip()

    bot_message = {"role": "assistant", "content": response}
    messages.append(bot_message)

    # DynamoDB への保存
    timestamp = datetime.now(pytz.timezone('Asia/Tokyo'))
    save_message_to_dynamodb(st.session_state['session_id'], timestamp, bot_message["content"], 'assistant')

    st.session_state["user_input"] = ""  # 入力欄を消去

# DDB から全てのメッセージを取得する関数
def read_all_messages_from_dynamodb():
    # 全てのメッセージを取得するためのScanを行います。
    response = table.scan()
    return response['Items']


# ユーザーインターフェイスの構築
st.set_page_config(page_title="Icelandic Chatbot", page_icon="🧊")
st.title("Icelandic Chatbot")

user_input = st.text_input("メッセージを入力してください。", key="user_input", on_change=communicate)

if st.session_state["messages"]:
    messages = st.session_state["messages"]

    for message in reversed(messages[1:]):  # 直近のメッセージを上に
        speaker = "🙂"
        if message["role"]=="assistant":
            speaker="🤖"

        st.write(speaker + ": " + message["content"])


st.title("Chat History")
search_query = st.text_input("検索ワードを入力してください。")

if search_query:
    # 検索クエリを OpenSearch 用にフォーマット
    query = {
        "size": 25,
        "query": {
            "multi_match": {
                "query": search_query,
                "analyzer": "japanese_analyzer",
                "fields": ["sender", "message"]
            }
        }
    }
    index_name = "chat_bot_history"
    results = search_in_opensearch(query, index_name)

    # 結果を保存するためのデータフレームのリストを作成する
    dataframes = []

    if results["hits"]["hits"]:
        for hit in results["hits"]["hits"]:
            # _source内の"sender", "message"と"timestamp"を取り出す
            sender = hit["_source"]["sender"]
            message = hit["_source"]["message"]
            timestamp = pd.to_datetime(hit["_source"]["timestamp"]) 
            formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S") #タイムスタンプ形式を変更

            # データフレームに結果を追加する
            new_row = pd.DataFrame({"Sender": [sender], "Message": [message], "Timestamp": [formatted_timestamp]})
            dataframes.append(new_row)

        # データフレームを結合する
        df = pd.concat(dataframes, ignore_index=True)

        # Streamlitを使用してデータフレームを表示する
        st.write(df)
    else:
        st.write("検索結果はありません。")
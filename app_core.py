from flask import Flask, render_template
import os
import configparser
import threading
import psycopg2
from flask import Flask, abort, redirect, render_template, request, url_for, flash, Response
from flask_httpauth import HTTPBasicAuth
from flask_socketio import SocketIO, emit, send
import pandas as pd
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, URITemplateAction, ConfirmTemplate, PostbackEvent, PostbackTemplateAction
from linebot.exceptions import LineBotApiError, InvalidSignatureError
# from models import botTalk, callDatabase, bind_phone
from urllib.parse import parse_qsl

app = Flask(__name__)


config = configparser.ConfigParser()
config.read("config.ini")

handler = WebhookHandler(config.get("line-bot", "channel_secret"))
line_bot_api = LineBotApi(config.get("line-bot", "channel_access_token"))


DATABASE_URL = os.environ["DATABASE_URL"]

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/create')
def create_table():
    """在資料庫中建立資料表"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        cursor = conn.cursor()


                #定義建立資料表的查詢
        create_query = """
            CREATE TABLE IF NOT EXISTS basic_data_table (
                serial_id serial NOT NULL,
                name text NOT NULL,
                birth_day VARCHAR(255) NOT NULL, -- 改用 VARCHAR
                phone1 VARCHAR(255) NOT NULL, -- 改用 VARCHAR
                phone2 VARCHAR(255) NOT NULL, -- 改用 VARCHAR
                personid VARCHAR(255) NOT NULL,
                PRIMARY KEY (serial_id)
            )
        """

        cursor.execute(create_query)
        print("Create basic_data_table successfully.")
        cursor.close()
        conn.close()
        return "basic_data_table created successfully."
    except Exception as e:
        print(f"An error occurred while creating the basic_data_table: {e}")
        return f"An error occurred while creating the basic_data_table: {e}"
    
@app.route('/upload_basic_data')
def upload():
    return render_template('upload_basic_data.html')


@app.route('/send_basic_data', methods=['POST'])
def send_basic_data_file():
    try:
        if 'file' not in request.files:
            return 'No file part when upload basic datat'

        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('index'))

        if file:
            df = pd.read_csv(file, encoding='big5')
            for index, row in df.iterrows():
                pt_id = row[0]
                pt_name = row[1]
                pt_birth_day = row[2]
                pt_phone1 =row[3]
                pt_phone2 = row[4]
                pt_person_id = row [5]

            return 'upload basic data'

        return 'Upload basic data error'
    except Exception as e:
        # 打印錯誤信息到控制台，或考慮使用日誌記錄
        print(f"Error when upload basic data: {e}")
        return str(e)




#-------------------------以下是衛教訊息傳送

submissions = []  # 保存提交的清單
sent_submissions = set()  # 保存已送出的項目
failed_submissions = {}  # 保存失敗的項目，使用字典而不是集合
coding_charts = []  # 定义一个空列表来存储 coding 值


user_id = 'U879e3796fbb1185b9654c34152d07ed9'

@app.route('/send_message', methods=['GET', 'POST'])
def send_message():

    query_data = select_coding()
    for row in query_data:
        coding_charts.append(row[1])  # 假设 coding 是第二个字段
    print(coding_charts)
    
    message_status = None
    if request.method == 'POST':
        if 'submit_form' in request.form:
            # 處理表單提交
            phone = request.form['phone']
            option = request.form['option']
            submission = f"{phone}, {option}"
            submissions.append(submission)

        elif 'send' in request.form:
            submission_to_send = request.form['send']
            message_status = send_message_steps(*submission_to_send.split(', '))
            if message_status == "訊息已發送":
                sent_submissions.add(submission_to_send)
            elif message_status == "尚未綁定":
                failed_submissions[submission_to_send] = "尚未綁定"
            else:
                failed_submissions[submission_to_send] = message_status

    return render_template('send_message.html', 
                           coding_charts=coding_charts,
                           submissions=submissions, 
                           sent_submissions=sent_submissions,
                           failed_submissions=failed_submissions)



def select_coding():
    """檢查資料庫有哪些coding"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()

        # 使用參數化查詢來提高安全性
        select_query = "SELECT * FROM education_message_coding_table"
        cursor.execute(select_query)
        query_data = cursor.fetchall()
        cursor.close()
        conn.close()

        return query_data   # 如果找到，返回查詢結果

    except Exception as e:
        print(f"An error occurred while selecting data: {e}")
        return []  # 發生錯誤時返回空列表

def select_phone(user_phone):
    """檢查資料庫中是否存在給定的用戶 phone"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()

        # 使用參數化查詢來提高安全性
        select_query = f"SELECT * FROM id_table11 WHERE number = '{user_phone}'"
        cursor.execute(select_query, (user_phone,))
        query_data = cursor.fetchall()
        cursor.close()
        conn.close()

        return query_data   # 如果找到，返回查詢結果

    except Exception as e:
        print(f"An error occurred while selecting data: {e}")
        return []  # 發生錯誤時返回空列表


def send_message_steps(user_phone, option):
    """處理電話綁定邏輯"""
    try:
        query_data = select_phone(user_phone)
        # query_data2 = select_coding_data(option)
        if len(query_data) == 0:
            return "尚未綁定"

        user_id = query_data[0][1]  # 假設 user_id 在查詢結果的第二列
        # education_message = query_data2[0][2]
        try:
            
            line_bot_api.push_message(user_id, TextSendMessage(text=option))
            return "訊息已發送"
        except Exception as e:
            return "發送失敗"

    except Exception as e:
        return f"處理錯誤: {e}"
    
def select_coding_data(option):
    """檢查coding對應的message"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()

        # 使用參數化查詢來提高安全性
        select_query = f"SELECT * FROM education_message_coding_table WHERE coding = '{option}'"
        cursor.execute(select_query)
        query_data = cursor.fetchall()
        cursor.close()
        conn.close()

        return query_data   # 如果找到，返回查詢結果

    except Exception as e:
        print(f"An error occurred while selecting data: {e}")
        return []  # 發生錯誤時返回空列表

@app.route('/send_education_message_coding_table', methods=['POST'])
def send_education_message_coding_table():
    try:
        if 'education_message_coding_table' not in request.files:
            return 'No coding_table file part'

        file = request.files['education_message_coding_table']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('index'))
        if file:
            df = pd.read_csv(file)
            # coding_charts = []  # 定义一个空列表来存储 coding 值
            truncate_education_message_coding_table()
            for index, row in df.iterrows():
                coding = row[0]
                education_message = row[1]
                renew_education_message_coding_table(coding, education_message)
            #     coding_charts.append(coding)  # 将 coding 添加到列表中
            # print(coding_charts)
            # return render_template('send_message.html', coding_charts=coding_charts)

        # if file:
        #     df = pd.read_csv(file)
        #     for index, row in df.iterrows():
        #         coding = row[0]
        #         education_message = row[1]
        #         renew_education_message_coding_table(coding,education_message)

            return 'Messages sent'

        return 'Upload error'
    except Exception as e:
        # 打印錯誤信息到控制台，或考慮使用日誌記錄
        print(f"Error: {e}")
        return str(e)

def truncate_education_message_coding_table():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        cursor = conn.cursor()

        # 使用 TRUNCATE 语句清空表
        truncate_query = "TRUNCATE TABLE education_message_coding_table"
        cursor.execute(truncate_query)

        conn.commit()
        cursor.close()
        conn.close()
        print("education_message_coding_table truncated successfully.")
    except Exception as e:
        print(f"An error occurred while inserting or truncating data: {e}")


def renew_education_message_coding_table(coding, education_message):
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        cursor = conn.cursor()

        # 插入新记录，使用参数化查询
        insert_query = "INSERT INTO education_message_coding_table (coding, education_message) VALUES (%s, %s)"
        cursor.execute(insert_query, (coding, education_message))
        
        conn.commit()
        cursor.close()
        conn.close()
        print("education_message_coding_table renewed successfully.")
    except Exception as e:
        print(f"An error occurred while inserting or truncating data: {e}")


if __name__ == '__main__':
    app.run(debug=True)

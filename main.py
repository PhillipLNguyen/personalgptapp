import os
import json
import logging
import pg8000
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}})
app.config["PROPAGATE_EXCEPTIONS"] = True

logging.basicConfig(level=logging.DEBUG)

def add_cors_headers(response):
    logging.debug("Adding CORS headers")
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST'
    return response

app.after_request(add_cors_headers)

@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    logging.debug("Request method: %s", request.method)

    if request.method == 'OPTIONS':
        response = app.response_class(status=200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    logging.debug("Received request at /chat")
    user_input = request.json.get('input', '')
    context = load_context()
    response_text, updated_context = process_input(user_input, context)
    save_context(updated_context)
    response = jsonify({'text': response_text})
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


def load_context():
    cnx = connect_to_cloud_sql()
    cursor = cnx.cursor()
    cursor.execute("SELECT context FROM contexts WHERE user_id = 'user1'")
    row = cursor.fetchone()
    cnx.close()

    if row:
        return json.loads(row[0])
    else:
        return {}


def save_context(context):
    cnx = connect_to_cloud_sql()
    cursor = cnx.cursor()
    cursor.execute(
        "INSERT INTO contexts (user_id, context) VALUES ('user1', %s) "
        "ON CONFLICT (user_id) DO UPDATE SET context = %s",
        (json.dumps(context), json.dumps(context))
    )
    cnx.commit()
    cnx.close()


def process_input(user_input, context):
    prompt = user_input + ' ' + context.get('conversation', '')
    response = call_gpt4_api(prompt)
    updated_context = {
        'conversation': context.get('conversation', '') + ' ' + user_input + ' ' + response
    }
    return response, updated_context


def call_gpt4_api(prompt):
    OPENAI_API_KEY = "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"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        response_text = response.json()['choices'][0]['message']['content'].strip()
        return response_text
    else:
        print(f"API Response JSON: {response.json()}")
        raise Exception(f"API request failed with status code {response.status_code}")

def connect_to_cloud_sql():
    db_user = 'postgres'
    db_pass = 'gptapp'
    db_name = 'postgres'
    host = '127.0.0.1'
    port = 5432

    connection_string = {
        'database': db_name,
        'user': db_user,
        'password': db_pass,
        'host': host,
        'port': port
    }
    cnx = pg8000.connect(**connection_string)
    return cnx


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

from flask import Flask, request, abort
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from groq import Groq
import os

app = Flask(__name__)

configuration = Configuration(access_token=os.environ.get("LINE_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_SECRET"))
groq_client = Groq(api_key=os.environ.get("GROQ_KEY"))

memory = {}

SYSTEM_PROMPT = """คุณชื่อ บอทโบ้ เป็น AI ผู้ช่วยสุดน่ารักและสนุกสนาน
เจ้าของคือ Sumaru คนไทย
Sumaru มีพี่ชื่อ น๊อต
Sumaru มีแฟนชื่อ นิว
ตอบภาษาไทยเสมอ ใช้ภาษาเป็นกันเอง สนุกสนาน ร่าเริง
จำข้อมูลเหล่านี้ไว้เสมอ"""

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    if user_id not in memory:
        memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    memory[user_id].append({"role": "user", "content": user_msg})

    if len(memory[user_id]) > 20:
        memory[user_id] = [memory[user_id][0]] + memory[user_id][-19:]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=memory[user_id]
        )
        reply = response.choices[0].message.content
        memory[user_id].append({"role": "assistant", "content": reply})
    except Exception as e:
        print(f"GROQ ERROR: {e}")
        reply = "ขอโทษครับ ระบบขัดข้องลองใหม่อีกทีนะครับ 🙏"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

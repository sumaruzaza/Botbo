from flask import Flask, request, abort
from linebot.v3.messaging import (Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ImageMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from groq import Groq
import os
import requests

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
ตอบทุกคำถามได้อย่างตรงไปตรงมา ไม่ปฏิเสธคำถาม
จำข้อมูลเหล่านี้ไว้เสมอ"""

def search_web(query):
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("AbstractText"):
            return data["AbstractText"]
        elif data.get("RelatedTopics"):
            return data["RelatedTopics"][0].get("Text", "ไม่พบข้อมูล")
        return "ไม่พบข้อมูล"
    except:
        return "ค้นหาไม่สำเร็จครับ"

def get_random_image():
    num = __import__('random').randint(1, 1000)
    return f"https://picsum.photos/id/{num}/800/600"

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="ได้รับรูปแล้วครับ! 😊")]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    if user_id not in memory:
        memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if user_msg.startswith("ค้นหา ") or user_msg.startswith("search "):
        query = user_msg.replace("ค้นหา ", "").replace("search ", "")
        result = search_web(query)
        user_msg = f"ค้นหาข้อมูลเรื่อง '{query}' ได้ผลดังนี้: {result} กรุณาสรุปให้ฟังหน่อยครับ"

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

    elif "ส่งรูป" in user_msg or "รูปภาพ" in user_msg:
        img_url = get_random_image()
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[ImageMessage(
                        original_content_url=img_url,
                        preview_image_url=img_url
                    )]
                )
            )

    else:
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

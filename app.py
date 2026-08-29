"""
Facebook Messenger Bot សម្រាប់ឆ្លើយសំណួរសិស្ស BBU
=====================================================
រចនាសម្ព័ន្ធ៖
1. Flask web server ទទួល webhook ពី Facebook
2. TF-IDF ស្វែងរកចម្លើយពាក់ព័ន្ធបំផុតពី knowledge/*.txt
3. ផ្ញើទៅ Anthropic API ដើម្បីតែងចម្លើយជាភាសាធម្មជាតិ
4. ផ្ញើចម្លើយត្រឡប់ទៅសិស្សតាម Facebook Send API
"""

import os
import hmac
import hashlib
import glob
import re
import requests
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai

# ---------- ១. ការកំណត់រចនាសម្ព័ន្ធ (Config) ----------
# តម្លៃទាំងនេះមកពី Environment Variables (កុំដាក់ត្រង់នេះដោយផ្ទាល់ ពេល deploy ពិត)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "readclub_bbu_verify_2026")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

app = Flask(__name__)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# ---------- ២. ផ្ទុក Knowledge Base ចូល memory ពេល server ចាប់ផ្តើម ----------
def load_knowledge_base(folder="knowledge"):
    """អានឯកសារ .txt ទាំងអស់ក្នុង folder knowledge/ ហើយញែកជា Q&A pairs"""
    qa_pairs = []
    for filepath in glob.glob(os.path.join(folder, "*.txt")):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # ញែកតាមទម្រង់ "Q: ... \n A: ..."
        blocks = re.findall(r"Q:\s*(.+?)\s*\nA:\s*(.+?)(?=\n\n|\nQ:|\Z)", content, re.DOTALL)
        for question, answer in blocks:
            answer = answer.strip()
            # រំលងចម្លើយដែលមិនទាន់បំពេញ
            if answer.startswith("[") and answer.endswith("]"):
                continue
            qa_pairs.append({"question": question.strip(), "answer": answer})
    return qa_pairs

knowledge_base = load_knowledge_base()
questions_list = [qa["question"] for qa in knowledge_base]

# TF-IDF vectorizer សម្រាប់ស្វែងរកសំណួរដែលស្រដៀងគ្នាបំផុត
vectorizer = None
question_vectors = None
if questions_list:
    vectorizer = TfidfVectorizer()
    question_vectors = vectorizer.fit_transform(questions_list)


def find_relevant_context(user_message, top_k=3):
    """ស្វែងរក Q&A ពាក់ព័ន្ធបំផុត ៣ ជាមួយសំណួររបស់សិស្ស"""
    if not vectorizer or not knowledge_base:
        return []
    user_vec = vectorizer.transform([user_message])
    similarities = cosine_similarity(user_vec, question_vectors).flatten()
    top_indices = similarities.argsort()[-top_k:][::-1]
    results = []
    for idx in top_indices:
        if similarities[idx] > 0.05:  # ចោលចោលបើមិនពាក់ព័ន្ធសោះ
            results.append(knowledge_base[idx])
    return results


# ---------- ៣. ហៅ Anthropic API ដើម្បីតែងចម្លើយ ----------
def generate_answer(user_message):
    context_items = find_relevant_context(user_message)
    if context_items:
        context_text = "\n\n".join(
            f"សំណួរ: {qa['question']}\nចម្លើយ: {qa['answer']}" for qa in context_items
        )
        system_prompt = (
            "អ្នកគឺជាជំនួយការឆ្លើយសំណួរសម្រាប់សិស្សថ្នាក់ទី១២ដែលចាប់អារម្មណ៍ចូលរៀននៅ "
            "Build Bright University (BBU)។ ប្រើព័ត៌មានខាងក្រោមដើម្បីឆ្លើយសំណួរអ្នកប្រើប្រាស់ "
            "ជាភាសាខ្មែរ ដោយសង្ខេប ច្បាស់លាស់ និងគួរសម។ បើព័ត៌មានមិនគ្រប់គ្រាន់ សូមណែនាំឲ្យទាក់ទង"
            "ការិយាល័យចុះឈ្មោះដោយផ្ទាល់។\n\n"
            f"ព័ត៌មានយោង៖\n{context_text}"
        )
    else:
        system_prompt = (
            "អ្នកគឺជាជំនួយការឆ្លើយសំណួរសម្រាប់សិស្សថ្នាក់ទី១២ដែលចាប់អារម្មណ៍ចូលរៀននៅ "
            "Build Bright University (BBU)។ ចម្លើយជាភាសាខ្មែរ ដោយសង្ខេប និងគួរសម។ បើមិនប្រាកដច្បាស់ "
            "សូមណែនាំឲ្យទាក់ទងការិយាល័យចុះឈ្មោះដោយផ្ទាល់ ជំនួសការស្មានចម្លើយ។"
        )

    full_prompt = f"{system_prompt}\n\nសំណួរអ្នកប្រើប្រាស់៖ {user_message}"
    response = gemini_model.generate_content(
        full_prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=400),
    )
    return response.text


# ---------- ៤. ផ្ញើសារត្រឡប់ទៅ Facebook ----------
def send_message(recipient_id, message_text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
    }
    resp = requests.post(url, params=params, json=payload)
    if resp.status_code != 200:
        print("Send API error:", resp.text)


# ---------- ៥. Webhook Verification (GET request ពី Facebook) ----------
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


# ---------- ៦. ការត្រួតពិនិត្យសុវត្ថិភាព Signature ----------
def verify_signature(payload, signature_header):
    """ត្រួតពិនិត្យថា request នេះមកពី Facebook ពិតប្រាកដ (ការពារ spoofing)"""
    if not APP_SECRET or not signature_header:
        return False
    expected_hash = hmac.new(
        APP_SECRET.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    received_hash = signature_header.replace("sha256=", "")
    return hmac.compare_digest(expected_hash, received_hash)


# ---------- ៧. ទទួលសារពីសិស្ស (POST request ពី Facebook) ----------
@app.route("/webhook", methods=["POST"])
def handle_message():
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.get_data(), signature):
        return jsonify({"status": "invalid signature"}), 403

    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event and "text" in messaging_event["message"]:
                    user_text = messaging_event["message"]["text"]
                    try:
                        answer = generate_answer(user_text)
                    except Exception as e:
                        print("Error generating answer:", e)
                        answer = "សូមទោស! ឥឡូវនេះមានបញ្ហាបច្ចេកទេស សូមព្យាយាមម្តងទៀត ឬទាក់ទងផ្ទាល់។"
                    send_message(sender_id, answer)

    return jsonify({"status": "ok"}), 200


# ---------- ៨. Health check (សម្រាប់ Render ដឹងថា server រស់) ----------
@app.route("/", methods=["GET"])
def health_check():
    return "BBU Facebook Bot is running.", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

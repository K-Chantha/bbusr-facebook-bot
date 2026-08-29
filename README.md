# BBU Facebook Page Bot

## ឯកសារក្នុងគម្រោង
- `app.py` — Backend server ចម្បង (Flask)
- `knowledge/enrollment_info.txt` — Knowledge base (Q&A) — **ត្រូវបំពេញឲ្យពេញលេញមុន deploy**
- `requirements.txt` — Python packages ដែលត្រូវការ

## Environment Variables ដែលត្រូវកំណត់ (នៅលើ Render ឬ local `.env`)

| ឈ្មោះ | ពន្យល់ | យកមកពីណា |
|---|---|---|
| `VERIFY_TOKEN` | ពាក្យសម្ងាត់ដែលអ្នកគិតឡើងផ្ទាល់ | អ្នកកំណត់ខ្លួនឯង (ត្រូវដូចគ្នានឹង Facebook Webhook settings) |
| `PAGE_ACCESS_TOKEN` | Token ភ្ជាប់ Page | Meta App Dashboard > Messenger API Settings |
| `APP_SECRET` | លេខសម្ងាត់ App | Meta App Dashboard > App Settings > Basic |
| `GEMINI_API_KEY` | API Key របស់ Google Gemini | aistudio.google.com/app/apikey |

## ការសាកល្បងក្នុង Local (មុន Deploy)

```bash
pip install -r requirements.txt --break-system-packages
export VERIFY_TOKEN="readclub_bbu_verify_2026"
export PAGE_ACCESS_TOKEN="EAAxxxxx..."
export APP_SECRET="xxxxx..."
export GEMINI_API_KEY="xxxxx..."
python app.py
```

បន្ទាប់មកប្រើ **ngrok** ដើម្បីបង្ហាញ local server ជា public URL សម្រាប់សាកល្បង Webhook៖

```bash
ngrok http 5000
```

## ការ Deploy លើ Render (ដូចគម្រោង Telegram bot)

1. Push កូដនេះទៅ GitHub repository
2. នៅ Render > New > Web Service > ភ្ជាប់ GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. ដាក់ Environment Variables ទាំង ៤ (VERIFY_TOKEN, PAGE_ACCESS_TOKEN, APP_SECRET, GEMINI_API_KEY) នៅក្នុង Render Dashboard (Environment tab)
6. Deploy — Render នឹងផ្តល់ URL ដូចជា `https://your-app.onrender.com`
7. Webhook Callback URL សម្រាប់ដាក់ក្នុង Facebook = `https://your-app.onrender.com/webhook`

## ការដំឡើង Webhook នៅ Facebook

1. Meta App Dashboard > Messenger > Messenger API Settings
2. Callback URL: `https://your-app.onrender.com/webhook`
3. Verify Token: ដូចគ្នានឹងតម្លៃ `VERIFY_TOKEN`
4. ចុច "Verify and save"
5. Subscribe Fields: ជ្រើស `messages` និង `messaging_postbacks`

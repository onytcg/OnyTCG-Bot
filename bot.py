import asyncio
import os
import sys
import edge_tts
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ddgs import DDGS

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

conversation_memory = {}

SYSTEM_PROMPT = """
Sei OnyTCG.
Rispondi SEMPRE in italiano, in modo chiaro e diretto.

Hai la capacità di cercare su internet e di leggere il contenuto delle pagine web.
Quando ti vengono forniti i contenuti delle pagine, significa che le hai già aperte e lette.
Non dire mai che non puoi aprire i link.
Usa le informazioni fornite per rispondere.
"""

def get_page_content(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())
        return text[:3500]
    except Exception as e:
        print(f"Errore pagina {url}:", e)
        return ""

def search_web(query: str) -> str:
    try:
        results = []
        
        if "onytcg" in query.lower():
            results = list(DDGS().text("onytcg.it", region="it-it", max_results=5))
            results += list(DDGS().text("site:onytcg.it", region="it-it", max_results=3))
        else:
            results = list(DDGS().text(query, region="it-it", max_results=5))

        if not results:
            return ""

        text = ""
        seen_urls = set()
        
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            text += f"=== PAGINA {i} ===\n"
            text += f"Titolo: {title}\n"
            text += f"Riassunto: {body}\n"
            text += f"URL: {href}\n"
            
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"CONTENUTO LETTO:\n{content}\n"
            
            text += "\n"
        
        return text
    except Exception as e:
        print("Errore ricerca:", e)
        return ""

async def generate_voice(text: str, filename: str = "voice.mp3"):
    clean_text = text
    clean_text = clean_text.replace("*", "").replace("_", "").replace("#", "").replace("`", "")
    clean_text = clean_text.replace("\n", ". ")
    clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi")
    clean_text = clean_text.replace("onytcg.it", "oni ti ci gi punto it")
    
    communicate = edge_tts.Communicate(
        clean_text,
        "it-IT-GiuseppeMultilingualNeural",
        rate="-5%",
        pitch="+3Hz"
    )
    await communicate.save(filename)
    return filename

async def get_ai_response(user_id: int, message: str) -> str:
    if user_id not in conversation_memory:
        conversation_memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    search_results = search_web(message)
    
    if search_results:
        enhanced_message = f"""
Ho cercato e aperto le pagine per te.

Domanda: {message}

Ecco cosa ho trovato e letto:

{search_results}

Rispondi alla domanda usando queste informazioni. Hai già aperto e letto le pagine.
"""
    else:
        enhanced_message = message
    
    conversation_memory[user_id].append({"role": "user", "content": enhanced_message})
    
    if len(conversation_memory[user_id]) > 22:
        conversation_memory[user_id] = [conversation_memory[user_id][0]] + conversation_memory[user_id][-20:]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_memory[user_id],
        temperature=0.3,
        max_tokens=500
    )
    
    ai_reply = response.choices[0].message.content
    conversation_memory[user_id].append({"role": "assistant", "content": ai_reply})
    return ai_reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono OnyTCG 👋\nCome va? Dimmi pure!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    await update.message.chat.send_action(action="typing")
    
    reply = await get_ai_response(user_id, text)
    
    await update.message.reply_text(reply)
    
    try:
        voice_file = await generate_voice(reply)
        with open(voice_file, "rb") as audio:
            await update.message.reply_voice(voice=audio)
        os.remove(voice_file)
    except Exception as e:
        print("Errore voce:", e)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await update.message.chat.send_action(action="typing")
    
    voice_file = await update.message.voice.get_file()
    await voice_file.download_to_drive("user_voice.ogg")
    
    with open("user_voice.ogg", "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            language="it"
        )
    
    user_text = transcription.text
    os.remove("user_voice.ogg")
    
    reply = await get_ai_response(user_id, user_text)
    
    await update.message.reply_text(reply)
    
    try:
        voice_file = await generate_voice(reply)
        with open(voice_file, "rb") as audio:
            await update.message.reply_voice(voice=audio)
        os.remove(voice_file)
    except Exception as e:
        print("Errore voce:", e)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("OnyTCG è online! 🟢")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())

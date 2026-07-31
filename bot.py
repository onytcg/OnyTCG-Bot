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
Sei OnyTCG, un ragazzo giovane e simpatico.
Rispondi SEMPRE in italiano, in modo naturale, breve e diretto.
Rispondi SOLO alla domanda fatta.
Non inventare informazioni.
Se non trovi niente di concreto, dillo chiaramente.
Quando trovi link, mettili nella risposta.
Il sito ufficiale è https://onytcg.it
"""

def get_page_content(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())[:2000]
    except:
        return ""

def search_web(query: str) -> str:
    try:
        results = []
        
        # Ricerca web normale
        results += list(DDGS().text(query, region="it-it", max_results=4))
        
        # Ricerca social
        words = query.lower().split()
        if len(words) >= 2:
            results += list(DDGS().text(f"{query} facebook", region="it-it", max_results=2))
            results += list(DDGS().text(f"{query} instagram", region="it-it", max_results=2))
            results += list(DDGS().text(f"{query} linkedin", region="it-it", max_results=2))
            results += list(DDGS().text(f'"{query}"', region="it-it", max_results=2))

        if not results:
            return ""

        text = ""
        seen = set()
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            
            key = title + href
            if key in seen:
                continue
            seen.add(key)
            
            text += f"{i}. {title}\n{body}\nLink: {href}\n"
            
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"Contenuto: {content}\n"
            text += "\n"
        
        return text
    except Exception as e:
        print("Errore ricerca:", e)
        return ""

async def generate_voice(text: str, filename: str = "voice.mp3"):
    clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "").replace("\n", ". ")
    clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi").replace("onytcg.it", "oni ti ci gi punto it")
    
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
Domanda: {message}

Risultati della ricerca (web + social):
{search_results}

Rispondi in modo breve e preciso usando solo queste informazioni.
Se non trovi niente di concreto, dillo chiaramente.
Se trovi link utili, mettili nella risposta.
"""
    else:
        enhanced_message = message
    
    conversation_memory[user_id].append({"role": "user", "content": enhanced_message})
    
    if len(conversation_memory[user_id]) > 20:
        conversation_memory[user_id] = [conversation_memory[user_id][0]] + conversation_memory[user_id][-18:]
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=conversation_memory[user_id],
        temperature=0.3,
        max_tokens=350
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
    
    try:
        reply = await get_ai_response(user_id, text)
        await update.message.reply_text(reply)
        
        voice_file = await generate_voice(reply)
        with open(voice_file, "rb") as audio:
            await update.message.reply_voice(voice=audio)
        os.remove(voice_file)
    except Exception as e:
        print("Errore:", e)
        await update.message.reply_text("Scusa, riprova pure.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await update.message.chat.send_action(action="typing")
    
    try:
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
        
        voice_file = await generate_voice(reply)
        with open(voice_file, "rb") as audio:
            await update.message.reply_voice(voice=audio)
        os.remove(voice_file)
    except Exception as e:
        print("Errore:", e)
        await update.message.reply_text("Scusa, riprova pure.")

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

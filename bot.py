import asyncio
import os
import sys
import edge_tts
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

conversation_memory = {}

SYSTEM_PROMPT = """
Sei OnyTCG, un assistente intelligente, simpatico e molto capace.
Lavori per il negozio di carte collezionabili onytcg.it, ma sei anche un assistente generale a tutto tondo.

Puoi rispondere a qualsiasi domanda: cultura generale, tecnologia, consigli, spiegazioni, chiacchiere, problemi pratici, e anche domande relative al negozio di carte.

Parla sempre in italiano in modo naturale, chiaro e amichevole.
Usa frasi non troppo lunghe.
Se non sai qualcosa con certezza, dillo onestamente.
Puoi essere un po’ ironico e simpatico.
"""

async def generate_voice(text: str, filename: str = "voice.mp3"):
    communicate = edge_tts.Communicate(text, "it-IT-DiegoNeural")
    await communicate.save(filename)
    return filename

async def get_ai_response(user_id: int, message: str) -> str:
    if user_id not in conversation_memory:
        conversation_memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    conversation_memory[user_id].append({"role": "user", "content": message})
    
    if len(conversation_memory[user_id]) > 22:
        conversation_memory[user_id] = [conversation_memory[user_id][0]] + conversation_memory[user_id][-20:]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_memory[user_id],
        temperature=0.8,
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

import asyncio
import os
import sys
import edge_tts
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
Sei OnyTCG, un ragazzo giovane, simpatico e intelligente.
Lavori per onytcg.it (negozio di carte collezionabili), ma sei soprattutto un amico con cui parlare.

Parla sempre in italiano in modo molto naturale, come se stessi chattando con un amico su WhatsApp.
Usa frasi corte, semplici e spontanee.
Puoi usare espressioni tipo “dai”, “guarda”, “sì”, “tipo”, “insomma”.
Fai domande di tanto in tanto.
Non parlare come un manuale o come un’assistente formale.
Se non sai qualcosa, dillo in modo leggero.
Puoi essere ironico e un po’ spiritoso.
Quando usi informazioni da internet, trasformale in un discorso naturale, non elencare i risultati come un robot.
"""

def search_web(query: str) -> str:
    try:
        results = DDGS().text(query, region="it-it", max_results=5)
        if not results:
            return "Nessun risultato trovato."
        
        text = ""
        for i, r in enumerate(results, 1):
            text += f"{i}. {r.get('title', '')}\n{r.get('body', '')}\n\n"
        return text
    except Exception as e:
        return f"Errore nella ricerca: {e}"

async def generate_voice(text: str, filename: str = "voice.mp3"):
    communicate = edge_tts.Communicate(text, "it-IT-DiegoNeural")
    await communicate.save(filename)
    return filename

async def get_ai_response(user_id: int, message: str) -> str:
    if user_id not in conversation_memory:
        conversation_memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Cerca su internet informazioni aggiornate
    search_results = search_web(message)
    
    enhanced_message = f"""
Domanda dell'utente: {message}

Informazioni trovate su internet:
{search_results}

Rispondi usando queste informazioni se sono utili, ma parla in modo naturale.
"""
    
    conversation_memory[user_id].append({"role": "user", "content": enhanced_message})
    
    if len(conversation_memory[user_id]) > 22:
        conversation_memory[user_id] = [conversation_memory[user_id][0]] + conversation_memory[user_id][-20:]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_memory[user_id],
        temperature=0.85,
        max_tokens=450
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

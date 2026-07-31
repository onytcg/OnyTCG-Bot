import os
import tempfile
import gradio as gr
import edge_tts
from openai import OpenAI
from ddgs import DDGS
import asyncio

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

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

def generate_voice_sync(text: str) -> str:
    clean_text = text
    clean_text = clean_text.replace("*", "").replace("_", "").replace("#", "").replace("`", "")
    clean_text = clean_text.replace("\n", ". ")
    clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi")
    clean_text = clean_text.replace("Onytcg", "Oni Ti Ci Gi")
    clean_text = clean_text.replace("onytcg.it", "oni ti ci gi punto it")
    clean_text = clean_text.replace("Onytcg.it", "oni ti ci gi punto it")

    filename = tempfile.mktemp(suffix=".mp3")
    
    async def _generate():
        communicate = edge_tts.Communicate(
            clean_text,
            "it-IT-GiuseppeMultilingualNeural",
            rate="-5%",
            pitch="+3Hz"
        )
        await communicate.save(filename)
    
    asyncio.run(_generate())
    return filename

def chat(message, history):
    search_results = search_web(message)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for human, assistant in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": assistant})
    
    enhanced = f"""
Domanda dell'utente: {message}

Informazioni trovate su internet:
{search_results}

Rispondi usando queste informazioni se sono utili, ma parla in modo naturale.
"""
    messages.append({"role": "user", "content": enhanced})
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.85,
        max_tokens=450
    )
    
    reply = response.choices[0].message.content
    voice_file = generate_voice_sync(reply)
    
    return reply, voice_file

with gr.Blocks(title="OnyTCG") as demo:
    gr.Markdown("# OnyTCG 🤖\nIl tuo assistente personale")
    
    chatbot = gr.Chatbot(height=400)
    msg = gr.Textbox(placeholder="Scrivi qui...", label="Messaggio")
    audio_out = gr.Audio(label="Risposta vocale", autoplay=True)
    
    def respond(message, history):
        reply, voice = chat(message, history)
        history = history + [(message, reply)]
        return history, "", voice
    
    msg.submit(respond, [msg, chatbot], [chatbot, msg, audio_out])

demo.launch(server_name="0.0.0.0", server_port=7860)

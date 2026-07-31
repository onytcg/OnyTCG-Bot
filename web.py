import os
import tempfile
import gradio as gr
from openai import OpenAI
import edge_tts
import asyncio

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Sei OnyTCG, un ragazzo giovane e simpatico.
Rispondi SEMPRE in italiano, in modo naturale, breve e diretto.
Rispondi SOLO alla domanda fatta.
Non inventare storie o collegamenti inutili.
Se la domanda è semplice, rispondi in modo semplice.
"""

def generate_voice(text: str):
    try:
        clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "").replace("\n", ". ")
        clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi").replace("onytcg.it", "oni ti ci gi punto it")
        filename = tempfile.mktemp(suffix=".mp3")
        
        async def _gen():
            communicate = edge_tts.Communicate(clean_text, "it-IT-GiuseppeMultilingualNeural", rate="-5%", pitch="+3Hz")
            await communicate.save(filename)
        
        asyncio.run(_gen())
        return filename
    except Exception as e:
        print("Errore voce:", e)
        return None

def chat(message, history):
    try:
        if not message or not str(message).strip():
            return history or [], None, ""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Gestione sicura della history
        if history:
            for item in history:
                try:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        messages.append({"role": "user", "content": str(item[0])})
                        messages.append({"role": "assistant", "content": str(item[1])})
                except:
                    pass

        messages.append({"role": "user", "content": str(message)})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,
            max_tokens=300
        )

        reply = response.choices[0].message.content
        voice_file = generate_voice(reply)
        
        new_history = (history or []) + [(message, reply)]
        return new_history, voice_file, ""

    except Exception as e:
        print("Errore chat:", e)
        new_history = (history or []) + [(message, "Scusa, riprova pure.")]
        return new_history, None, ""

with gr.Blocks(title="OnyTCG") as demo:
    gr.Markdown("# OnyTCG 🤖\nIl tuo assistente personale")
    
    chatbot = gr.Chatbot(height=400)
    msg = gr.Textbox(placeholder="Scrivi qui...", label="Messaggio")
    audio_out = gr.Audio(label="Voce", autoplay=True)
    
    msg.submit(chat, [msg, chatbot], [chatbot, audio_out, msg])

demo.launch(server_name="0.0.0.0", server_port=7860)

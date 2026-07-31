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
            return "Scrivi pure!"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if history:
            for human, assistant in history:
                messages.append({"role": "user", "content": str(human)})
                messages.append({"role": "assistant", "content": str(assistant)})

        messages.append({"role": "user", "content": str(message)})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,
            max_tokens=300
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Errore:", e)
        return "Scusa, riprova pure."

demo = gr.ChatInterface(
    fn=chat,
    title="OnyTCG 🤖",
    description="Il tuo assistente personale"
)

demo.launch(server_name="0.0.0.0", server_port=7860)

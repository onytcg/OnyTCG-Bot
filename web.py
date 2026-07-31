import os
import tempfile
import gradio as gr
from openai import OpenAI
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
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
Non inventare storie, film, libri o collegamenti inutili.
Se la domanda è semplice (tipo "ci sei?", "ciao", "come stai"), rispondi in modo semplice.
Non allungare inutilmente le risposte.
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
        results = list(DDGS().text(query, region="it-it", max_results=3))
        if not results:
            return ""
        text = ""
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            text += f"{i}. {title}\n{body}\n"
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"Contenuto: {content}\n"
            text += "\n"
        return text
    except:
        return ""

def generate_voice(text: str) -> str:
    try:
        clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "").replace("\n", ". ")
        clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi").replace("onytcg.it", "oni ti ci gi punto it")
        filename = tempfile.mktemp(suffix=".mp3")
        async def _gen():
            communicate = edge_tts.Communicate(clean_text, "it-IT-GiuseppeMultilingualNeural", rate="-5%", pitch="+3Hz")
            await communicate.save(filename)
        asyncio.run(_gen())
        return filename
    except:
        return None

def chat(message, history):
    try:
        if not message or not str(message).strip():
            return history, None, ""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if history:
            for item in history:
                try:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        messages.append({"role": "user", "content": str(item[0])})
                        messages.append({"role": "assistant", "content": str(item[1])})
                    elif isinstance(item, dict):
                        messages.append({"role": item.get("role", "user"), "content": str(item.get("content", ""))})
                except:
                    continue

        search_results = ""
        keywords = ["tempo", "meteo", "notizie", "sito", "onytcg", "prezzo", "oggi", "quando", "dove"]
        if any(k in message.lower() for k in keywords):
            search_results = search_web(str(message))

        if search_results:
            user_content = f"Domanda: {message}\n\nInfo trovate:\n{search_results}\n\nRispondi in modo breve e preciso."
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,
            max_tokens=300
        )

        reply = response.choices[0].message.content
        voice_file = generate_voice(reply)
        
        history = history + [(message, reply)]
        return history, voice_file, ""

    except Exception as e:
        print("Errore:", e)
        return history, None, ""

with gr.Blocks(title="OnyTCG") as demo:
    gr.Markdown("# OnyTCG 🤖\nIl tuo assistente personale")
    
    chatbot = gr.Chatbot(height=400)
    msg = gr.Textbox(placeholder="Scrivi qui...", label="Messaggio")
    audio_out = gr.Audio(label="Voce", autoplay=True)
    
    msg.submit(chat, [msg, chatbot], [chatbot, audio_out, msg])

demo.launch(server_name="0.0.0.0", server_port=7860)

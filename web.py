import os
import gradio as gr
from openai import OpenAI
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Sei OnyTCG, un assistente preciso e chiaro.
Rispondi SEMPRE in italiano.
Rispondi SOLO alla domanda fatta, in modo breve e preciso.
Quando ti vengono date informazioni da internet o dal contenuto di pagine web, usale.
Non inventare informazioni.
Non dire che non puoi cercare online.
"""

def get_page_content(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return ""
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        # Pulisce spazi multipli
        text = " ".join(text.split())
        return text[:3000]
    except Exception as e:
        print(f"Errore pagina {url}:", e)
        return ""

def search_web(query: str) -> str:
    try:
        results = list(DDGS().text(query, region="it-it", max_results=4))
        
        if not results:
            return ""

        text = ""
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            
            text += f"### {title}\n"
            text += f"Riassunto: {body}\n"
            text += f"Link: {href}\n"
            
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"Contenuto della pagina:\n{content}\n"
            
            text += "\n"
        
        return text
    except Exception as e:
        print("Errore ricerca:", e)
        return ""

def chat(message, history):
    try:
        if not message or not str(message).strip():
            return "Scrivi pure!"

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

        search_results = search_web(str(message))

        if search_results:
            user_content = f"""
Domanda: {message}

Informazioni trovate su internet (inclusi i contenuti delle pagine aperte):
{search_results}

Rispondi alla domanda in modo preciso usando solo queste informazioni.
"""
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.5,
            max_tokens=500
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

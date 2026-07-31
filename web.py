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
Sei OnyTCG, un ragazzo giovane e simpatico.
Rispondi SEMPRE in italiano, in modo breve e naturale.
Rispondi SOLO alla domanda fatta.

Quando ti vengono date informazioni da internet o dal contenuto di pagine web, usale per rispondere.
Non dire mai che non puoi cercare online o aprire link.
"""

def get_page_content(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Rimuove script e style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        return text[:2500]  # limita la lunghezza
    except:
        return ""

def search_web(query: str) -> str:
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, region="it-it", max_results=4):
                results.append(r)

        if not results:
            return ""

        text = ""
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            
            text += f"Titolo: {title}\nSnippet: {body}\nLink: {href}\n"
            
            # Apre e legge il contenuto della pagina
            if href:
                content = get_page_content(href)
                if content:
                    text += f"Contenuto della pagina:\n{content}\n"
            
            text += "\n---\n"
        
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
Domanda dell'utente: {message}

Risultati dalla ricerca e contenuto delle pagine:
{search_results}

Usa queste informazioni per rispondere alla domanda.
"""
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            max_tokens=450
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

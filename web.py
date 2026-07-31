import os
import tempfile
import streamlit as st
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

REGOLE DI PRECISIONE (obbligatorie):
1. Usa SOLO le informazioni che ti vengono fornite dalla ricerca.
2. Non inventare mai fatti, nomi, link o dettagli.
3. Se le informazioni non sono chiare o incomplete, dillo chiaramente.
4. Se non trovi niente di concreto, rispondi: "Non ho trovato informazioni precise su questo."
5. Quando trovi link, mettili nella risposta.
6. Il sito ufficiale è https://onytcg.it
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
        return " ".join(text.split())[:800]
    except:
        return ""

def search_web(query: str) -> str:
    try:
        results = []
        results += list(DDGS().text(query, region="it-it", max_results=2))
        
        words = query.lower().split()
        if len(words) >= 2:
            results += list(DDGS().text(f"{query} facebook", region="it-it", max_results=1))
            results += list(DDGS().text(f"{query} instagram", region="it-it", max_results=1))
            results += list(DDGS().text(f"{query} linkedin", region="it-it", max_results=1))

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
            
            text += f"{i}. {title}\n{body}\nLink: {href}\n\n"
            
            if href and "onytcg" in href.lower():
                content = get_page_content(href)
                if content:
                    text += f"Contenuto: {content}\n\n"
        
        return text[:3000]
    except Exception as e:
        print("Errore ricerca:", e)
        return ""

def generate_voice(text: str):
    try:
        clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "").replace("\n", ". ")
        clean_text = clean_text.replace("OnyTCG", "Oni Ti Ci Gi").replace("onytcg.it", "oni ti ci gi punto it")
        
        filename = tempfile.mktemp(suffix=".mp3")
        
        async def _gen():
            communicate = edge_tts.Communicate(
                clean_text,
                "it-IT-GiuseppeMultilingualNeural",
                rate="-5%",
                pitch="+3Hz"
            )
            await communicate.save(filename)
        
        asyncio.run(_gen())
        return filename
    except Exception as e:
        print("Errore voce:", e)
        return None

def transcribe_audio(audio_file):
    try:
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                language="it"
            )
        return transcription.text
    except Exception as e:
        print("Errore trascrizione:", e)
        return None

def get_ai_response(message, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for human, assistant in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": assistant})
    
    search_results = search_web(message)
    
    if search_results:
        user_content = f"""
Domanda: {message}

Risultati della ricerca (web + social):
{search_results}

Rispondi in modo breve e preciso usando SOLO queste informazioni.
Se non trovi niente di concreto, dillo chiaramente.
Se trovi link utili, mettili nella risposta.
"""
    else:
        user_content = message
    
    messages.append({"role": "user", "content": user_content})
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.2,
        max_tokens=300
    )
    
    return response.choices[0].message.content

# --- STREAMLIT UI ---
st.set_page_config(page_title="OnyTCG", page_icon="🤖")
st.title("OnyTCG 🤖")
st.caption("Il tuo assistente personale — parla o scrivi")

if "history" not in st.session_state:
    st.session_state.history = []

# Mostra la cronologia
for human, assistant in st.session_state.history:
    with st.chat_message("user"):
        st.write(human)
    with st.chat_message("assistant"):
        st.write(assistant)

# Input microfono
st.write("### 🎤 Parla con me")
audio_input = st.audio_input("Registra il tuo messaggio")

if audio_input is not None:
    # Salva l'audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_input.read())
        audio_path = tmp.name
    
    with st.spinner("Sto ascoltando..."):
        user_text = transcribe_audio(audio_path)
    
    if user_text:
        with st.chat_message("user"):
            st.write(user_text)
        
        with st.chat_message("assistant"):
            with st.spinner("Sto pensando..."):
                reply = get_ai_response(user_text, st.session_state.history)
                st.write(reply)
                
                voice_file = generate_voice(reply)
                if voice_file:
                    st.audio(voice_file, autoplay=True)
        
        st.session_state.history.append((user_text, reply))

# Input testo (opzionale)
if prompt := st.chat_input("Oppure scrivi qui..."):
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            reply = get_ai_response(prompt, st.session_state.history)
            st.write(reply)
            
            voice_file = generate_voice(reply)
            if voice_file:
                st.audio(voice_file, autoplay=True)
    
    st.session_state.history.append((prompt, reply))

import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI
from system import system_prompt

# -----------------------------
# Configuration & Setup
# -----------------------------

SYSTEM_PROMPT = system_prompt
EXCEL_FILE = "chat_history.xlsx"

# -----------------------------
# Streamlit UI Setup
# -----------------------------

st.set_page_config(
    page_title="LLM Tester & Chatbot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Model Testing Chatbot")
st.caption("Latency • Tokens • Cost Tracking")

# -----------------------------
# Sidebar Configuration Inputs
# -----------------------------

with st.sidebar:
    st.header("⚙️ API Configuration")
    
    base_url = st.text_input(
        "Base URL", 
        value="https://openrouter.ai/api/v1",
        help="Endpoint URL (e.g., https://openrouter.ai/api/v1 or https://api.deepinfra.com/v1/openai)"
    )
    
    api_key = st.text_input(
        "API Key", 
        type="password",
        value="",
        help="Enter your API key here"
    )
    
    model = st.text_input(
        "Model Name", 
        value="zai-org/GLM-5.1",
        help="Specify the model identifier (e.g., zai-org/GLM-5.1)"
    )

    st.subheader("💰 Pricing (per million tokens)")
    col1, col2 = st.columns(2)
    with col1:
        input_price = st.number_input("Input ($)", value=1.40, step=0.10)
    with col2:
        output_price = st.number_input("Output ($)", value=4.40, step=0.10)

    st.divider()

# -----------------------------
# Excel Helper Function
# -----------------------------

def save_chat(data):
    df = pd.DataFrame([data])
    if os.path.exists(EXCEL_FILE):
        old = pd.read_excel(EXCEL_FILE)
        df = pd.concat([old, df], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# -----------------------------
# Session State Initialization
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

# -----------------------------
# Display Previous Chat
# -----------------------------

for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            st.caption(
                f"Model: {msg.get('model', 'N/A')} | "
                f"Latency: {msg['latency']} s | "
                f"Prompt Tokens: {msg['prompt_tokens']} | "
                f"Completion Tokens: {msg['completion_tokens']} | "
                f"Cost: ${msg['cost']}"
            )

# -----------------------------
# User Input & Execution
# -----------------------------

prompt = st.chat_input("Type your message...")

if prompt:
    # Validate API Key before proceeding
    if not api_key:
        st.error("Please enter a valid API Key in the sidebar to proceed.")
        st.stop()

    # Instantiate client dynamically based on current UI inputs
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.display_messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # Assistant Response Generation
    with st.chat_message("assistant"):
        placeholder = st.empty()
        start = time.perf_counter()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=st.session_state.messages,
                max_tokens=500
            )

            latency = time.perf_counter() - start
            assistant = response.choices[0].message.content
            usage = response.usage

            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

            cost = (
                prompt_tokens * input_price / 1_000_000
                + completion_tokens * output_price / 1_000_000
            )

            tps = completion_tokens / latency if latency > 0 else 0

            placeholder.markdown(assistant)

            st.caption(
                f"Model: **{model}** | "
                f"Latency: **{latency:.3f}s** | "
                f"Prompt Tokens: **{prompt_tokens}** | "
                f"Completion Tokens: **{completion_tokens}** | "
                f"Total Tokens: **{total_tokens}** | "
                f"Tokens/sec: **{tps:.2f}** | "
                f"Cost: **${cost:.8f}**"
            )

            # Save assistant message in session
            st.session_state.display_messages.append(
                {
                    "role": "assistant",
                    "content": assistant,
                    "model": model,
                    "latency": round(latency, 3),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost": round(cost, 8)
                }
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": assistant
                }
            )

            # Save to Excel
            save_chat(
                {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Model": model,
                    "Base URL": base_url,
                    "User": prompt,
                    "Assistant": assistant,
                    "Latency(s)": round(latency, 3),
                    "Prompt Tokens": prompt_tokens,
                    "Completion Tokens": completion_tokens,
                    "Total Tokens": total_tokens,
                    "Tokens/sec": round(tps, 2),
                    "Cost($)": round(cost, 8)
                }
            )

        except Exception as e:
            st.error(f"Error calling model API: {e}")

# -----------------------------
# Sidebar Stats & Download
# -----------------------------

with st.sidebar:
    st.header("Chat Statistics")
    turns = len(
        [m for m in st.session_state.display_messages if m["role"] == "assistant"]
    )
    st.metric("Conversation Turns", turns)

    if st.button("Clear Chat"):
        st.session_state.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]
        st.session_state.display_messages = []
        st.rerun()

    if os.path.exists(EXCEL_FILE):
        with open(EXCEL_FILE, "rb") as f:
            st.download_button(
                "📥 Download Chat History",
                f,
                file_name="chat_history.xlsx"
            )
import streamlit as st
from difflib import ndiff
import pdfplumber
from docx import Document
import openai
import os

# -----------------------------
# 🔐 OpenAI API Key
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

# -----------------------------
# 📄 Extract text from file
# -----------------------------
def extract_text(file):
    if file.name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])

    elif file.name.endswith(".pdf"):
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    text += page.extract_text() + "\n"
        return text

    return ""

# -----------------------------
# 🤖 AI Editing Function
# -----------------------------
def get_ai_edit(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a legal editor. Make only minimal necessary edits. Do not rewrite entire text."
                },
                {
                    "role": "user",
                    "content": f"Edit this contract:\n{text}"
                }
            ]
        )

        return response['choices'][0]['message']['content']

    except Exception as e:
        return f"Error: {str(e)}"

# -----------------------------
# 🔍 Diff Function
# -----------------------------
def generate_diff(original, edited):
    diff = ndiff(original.split(), edited.split())

    result = []
    for word in diff:
        if word.startswith('- '):
            result.append(f"<del>{word[2:]}</del>")
        elif word.startswith('+ '):
            result.append(f"<ins>{word[2:]}</ins>")
        elif word.startswith('? '):
            continue
        else:
            result.append(word[2:])

    return " ".join(result)

# -----------------------------
# 🎯 UI
# -----------------------------
st.set_page_config(page_title="AI Contract Redliner", layout="wide")

st.title("📄 AI Contract Redliner (Mini FirstRead)")

uploaded_file = st.file_uploader("Upload Word or PDF", type=["docx", "pdf"])

original_text = ""

if uploaded_file:
    original_text = extract_text(uploaded_file)

    st.subheader("📥 Extracted Text")
    st.text_area("Original Contract", original_text, height=250)

    if st.button("✨ Run AI Review"):
        with st.spinner("AI is reviewing..."):
            edited_text = get_ai_edit(original_text)

        st.subheader("🤖 AI Edited Version")
        st.text_area("Edited Text", edited_text, height=250)

        st.subheader("🔍 Redline View")

        diff_html = generate_diff(original_text, edited_text)

        st.markdown(f"""
        <style>
        del {{ color: red; text-decoration: line-through; }}
        ins {{ color: green; text-decoration: underline; }}
        </style>
        {diff_html}
        """, unsafe_allow_html=True)

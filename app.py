import os
os.system('pip install openai>=1.0.0 python-docx')

import streamlit as st
import difflib
import re
from openai import OpenAI
from docx import Document
import io

# ... (the rest of your code stays exactly the same) ...
# ==========================================
# 1. PAGE CONFIGURATION & HTML DIFF LOGIC
# ==========================================
st.set_page_config(page_title="AI Contract Redliner", page_icon="📜", layout="wide")
st.title("📜 AI Contract Redliner (FirstRead Clone)")

def generate_html_diff(original, revised):
    orig_tokens = re.split(r'(\s+)', original)
    rev_tokens = re.split(r'(\s+)', revised)
    matcher = difflib.SequenceMatcher(None, orig_tokens, rev_tokens)
    html_output =[]
    
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        orig_snippet = "".join(orig_tokens[i1:i2])
        rev_snippet = "".join(rev_tokens[j1:j2])
        if opcode == 'equal':
            html_output.append(orig_snippet)
        elif opcode == 'delete':
            html_output.append(f'<del style="color: #b30000; background-color: #fadbd8; text-decoration: line-through;">{orig_snippet}</del>')
        elif opcode == 'insert':
            html_output.append(f'<ins style="color: #1e8449; background-color: #d5f5e3; text-decoration: none; font-weight: bold;">{rev_snippet}</ins>')
        elif opcode == 'replace':
            html_output.append(f'<del style="color: #b30000; background-color: #fadbd8; text-decoration: line-through;">{orig_snippet}</del>')
            html_output.append(f'<ins style="color: #1e8449; background-color: #d5f5e3; text-decoration: none; font-weight: bold;">{rev_snippet}</ins>')
            
    return "".join(html_output).replace('\n', '<br>')

# ==========================================
# 2. SIDEBAR (API Key & Playbook)
# ==========================================
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("OpenAI API Key", type="password")

st.sidebar.subheader("Company Playbook")
playbook_rules = st.sidebar.text_area(
    "Define your fallback rules:",
    value="1. Liability must be capped at fees paid in the prior 12 months.\n2. No unlimited indemnification.\n3. Governing law must be Delaware.",
    height=200
)

# ==========================================
# 3. MAIN UI (File Uploader)
# ==========================================
st.subheader("1. Upload Contract")
# THIS IS THE FILE UPLOADER WIDGET
uploaded_file = st.file_uploader("Upload a Word Document (.docx)", type=["docx"])

extracted_text = ""

if uploaded_file is not None:
    # Read the Word document into memory
    doc = Document(uploaded_file)
    # Extract paragraphs and join them together
    extracted_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    st.success("File uploaded and text extracted successfully!")

st.subheader("2. Review & Edit Text")
# Put the extracted text into the text area so the user can see it before running the AI
contract_text = st.text_area("Contract Text:", value=extracted_text, height=200)

# ==========================================
# 4. RUN THE AI
# ==========================================
if st.button("Generate Redlines", type="primary"):
    if not api_key:
        st.error("Please enter your OpenAI API Key in the sidebar.")
    elif not contract_text.strip():
        st.warning("Please upload a document or paste text.")
    else:
        with st.spinner("Analyzing against playbook and generating surgical edits..."):
            try:
                client = OpenAI(api_key=api_key)
                prompt = f"""You are a pragmatic contract reviewer. 
                Review the text below against this Playbook:
                {playbook_rules}
                
                CRITICAL INSTRUCTIONS:
                - Make the absolute MINIMAL edits necessary to comply.
                - If it already complies, return the EXACT original text.
                - Output ONLY the revised text. No conversational filler, no quotes.
                
                CLAUSE TO REVIEW:
                {contract_text}
                """
                
                response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                revised_text = response.choices[0].message.content.strip()
                
                st.divider()
                st.subheader("Visual Redlines")
                if contract_text == revised_text:
                    st.success("✅ This text complies with the playbook. No edits needed.")
                else:
                    html_diff = generate_html_diff(contract_text, revised_text)
                    st.markdown(f"""
                    <div style="background-color: white; color: black; padding: 20px; border-radius: 5px; border: 1px solid #ccc; font-family: 'Times New Roman', serif; font-size: 16px; line-height: 1.6;">
                        {html_diff}
                    </div>
                    """, unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"An error occurred: {e}")

import streamlit as st
import json
import os
import re
from docx import Document
import pdfplumber
import google.generativeai as genai

# ==========================================
# 1. PAGE CONFIGURATION & CHUNKING LOGIC
# ==========================================
st.set_page_config(page_title="Gemini Surgical Redliner", page_icon="📝", layout="wide")
st.title("📝 Surgical AI Redliner (Powered by Gemini)")
st.markdown("Processes the document chunk-by-chunk using Google's Gemini 1.5 Pro model.")

def chunk_text(text, max_chars=2500):
    """Splits text by paragraphs to ensure legal clauses are never cut in half."""
    paragraphs = re.split(r'\n+', text)
    chunks =[]
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# ==========================================
# 2. SIDEBAR (Load Playbook)
# ==========================================
st.sidebar.header("Configuration")

def load_playbook():
    if os.path.exists("playbook.json"):
        try:
            with open("playbook.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                formatted_playbook = ""
                for clause_name, rules_list in data.items():
                    formatted_playbook += f"=== {clause_name.upper()} ===\n"
                    for rule in rules_list:
                        formatted_playbook += f"- {rule}\n"
                    formatted_playbook += "\n"
                return formatted_playbook.strip()
        except Exception as e:
            return f"Error reading JSON: {e}"
    return "Error: playbook.json not found."

st.sidebar.subheader("Company Playbook")
playbook_rules = st.sidebar.text_area("Loaded from playbook.json:", value=load_playbook(), height=400)

# ==========================================
# 3. MAIN UI (File Uploader)
# ==========================================
st.subheader("1. Upload Contract")
uploaded_file = st.file_uploader("Upload a Contract (.docx or .pdf)", type=["docx", "pdf"])

extracted_text = ""

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            extracted_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        elif uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                pages_text =[page.extract_text() for page in pdf.pages if page.extract_text()]
                extracted_text = "\n".join(pages_text)
        st.success(f"Successfully extracted text from {uploaded_file.name}!")
    except Exception as e:
        st.error(f"Error reading file: {e}")

st.subheader("2. Review Text")
contract_text = st.text_area("Contract Text:", value=extracted_text, height=200)

# ==========================================
# 4. RUN THE SURGICAL AI (THE GEMINI LOOP)
# ==========================================
def load_prompt_template():
    if os.path.exists("prompt.txt"):
        with open("prompt.txt", "r", encoding="utf-8") as file:
            return file.read()
    return "Error: prompt.txt not found."

if st.button("Generate Surgical Redlines", type="primary"):
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("API Key missing! Please configure 'GEMINI_API_KEY' in Streamlit Secrets.")
    elif not contract_text.strip():
        st.warning("Please upload a document or paste text.")
    else:
        chunks = chunk_text(contract_text, max_chars=2500)
        all_edits =[]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 1. Authenticate with Google Gemini
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # 2. Set up the Gemini 1.5 Pro model with strict JSON formatting
            model = genai.GenerativeModel(
                'gemini-1.5-pro',
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0
                }
            )
            
            prompt_template = load_prompt_template()
            
            # THE MAGICAL LOOP
            for i, chunk in enumerate(chunks):
                status_text.text(f"Analyzing section {i+1} of {len(chunks)}...")
                
                # Inject playbook and chunk text into the prompt
                prompt = prompt_template.replace("{playbook_rules}", playbook_rules).replace("{contract_chunk}", chunk)
                
                # 3. Call the Gemini AI
                response = model.generate_content(prompt)
                
                # 4. Parse the JSON response from Gemini
                ai_response = json.loads(response.text)
                chunk_edits = ai_response.get("edits",[])
                
                if chunk_edits:
                    all_edits.extend(chunk_edits)
                
                progress_bar.progress((i + 1) / len(chunks))
            
            status_text.success("Review Complete!")
            st.divider()
            
            # ==========================================
            # 5. RENDER THE RESULTS (WITH TABS)
            # ==========================================
            st.subheader("Review Results")
            
            if not all_edits:
                st.success("✅ This text complies with the playbook. No edits needed.")
            else:
                tab1, tab2 = st.tabs(["🔴 Visual Redlines", "📄 Clean Final Text"])
                
                html_text = contract_text
                clean_text = contract_text
                
                edit_counter = 1
                justifications_text = ""
                
                for edit in all_edits:
                    old_text = edit.get("exact_old_text", "")
                    new_text = edit.get("exact_new_text", "")
                    justification = edit.get("justification", "")
                    
                    if old_text and old_text in html_text:
                        redline_html = f'<del style="color: #b30000; background-color: #fadbd8; text-decoration: line-through;">{old_text}</del> <ins style="color: #1e8449; background-color: #d5f5e3; text-decoration: none; font-weight: bold;">{new_text}</ins>'
                        html_text = html_text.replace(old_text, redline_html, 1)
                        clean_text = clean_text.replace(old_text, new_text, 1)
                        
                        justifications_text += f"**Edit {edit_counter}:** {justification}\n\n"
                        edit_counter += 1
                
                with tab1:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"""
                        <div style="background-color: white; color: black; padding: 20px; border-radius: 5px; border: 1px solid #ccc; font-family: 'Times New Roman', serif; font-size: 16px; line-height: 1.6;">
                            {html_text.replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown("### Justifications & Comments")
                        st.info(justifications_text)
                
                with tab2:
                    st.markdown("### Ready for Microsoft Word")
                    st.text_area("Copy this final text:", value=clean_text, height=400)

        except Exception as e:
            st.error(f"An error occurred: {e}")

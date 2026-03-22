import streamlit as st
import json
from openai import OpenAI 
from docx import Document
import pdfplumber
import os

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Surgical AI Redliner", page_icon="📜", layout="wide")
st.title("📜 Surgical AI Redliner")
st.markdown("Generates absolute minimal edits and provides negotiation justifications.")

# ==========================================
# 2. SIDEBAR (Load Playbook from JSON)
# ==========================================
st.sidebar.header("Configuration")

def load_playbook():
    if os.path.exists("playbook.json"):
        try:
            with open("playbook.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                
                # Format the JSON data into a clean, readable string
                formatted_playbook = ""
                for clause_name, rules_list in data.items():
                    formatted_playbook += f"=== {clause_name.upper()} ===\n"
                    for rule in rules_list:
                        formatted_playbook += f"- {rule}\n"
                    formatted_playbook += "\n"
                    
                return formatted_playbook.strip()
        except Exception as e:
            return f"Error reading JSON: {e}"
            
    return "Error: playbook.json not found. Please paste rules here."

default_playbook_text = load_playbook()

st.sidebar.subheader("Company Playbook")
playbook_rules = st.sidebar.text_area(
    "Loaded from playbook.json:",
    value=default_playbook_text,
    height=400
)

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
# 4. RUN THE SURGICAL AI
# ==========================================
def load_prompt_template():
    if os.path.exists("prompt.txt"):
        with open("prompt.txt", "r", encoding="utf-8") as file:
            return file.read()
    return "Error: prompt.txt not found."

if st.button("Generate Surgical Redlines", type="primary"):
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("API Key missing in Streamlit Secrets.")
    elif not contract_text.strip():
        st.warning("Please upload a document or paste text.")
    else:
        with st.spinner("Analyzing playbook and calculating surgical edits..."):
            try:
                client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                
                # 1. Load the prompt from the text file
                prompt_template = load_prompt_template()
                
                # 2. Inject the playbook and contract text into the prompt
                prompt = prompt_template.format(
                    playbook_rules=playbook_rules,
                    contract_text=contract_text
                )
                
                # 3. Call the AI
                response = client.chat.completions.create(
                    model="gpt-4o", 
                    response_format={ "type": "json_object" }, # Forces strict JSON
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                
                # Parse the JSON response
                ai_response = json.loads(response.choices[0].message.content)
                edits = ai_response.get("edits",[])
                
                st.divider()
                st.subheader("Review Results")
                
                if not edits:
                    st.success("✅ This text complies with the playbook. No edits needed.")
                else:
                    col1, col2 = st.columns([2, 1])
                    
                    html_text = contract_text
                    
                    with col2:
                        st.markdown("### Justifications & Comments")
                    
                    for i, edit in enumerate(edits):
                        old_text = edit.get("exact_old_text", "")
                        new_text = edit.get("exact_new_text", "")
                        justification = edit.get("justification", "")
                        
                        if old_text and old_text in html_text:
                            redline_html = f'<del style="color: #b30000; background-color: #fadbd8; text-decoration: line-through;">{old_text}</del> <ins style="color: #1e8449; background-color: #d5f5e3; text-decoration: none; font-weight: bold;">{new_text}</ins>'
                            html_text = html_text.replace(old_text, redline_html)
                        
                        with col2:
                            st.info(f"**Edit {i+1}:** {justification}")
                            
                    with col1:
                        st.markdown("### Visual Redlines")
                        st.markdown(f"""
                        <div style="background-color: white; color: black; padding: 20px; border-radius: 5px; border: 1px solid #ccc; font-family: 'Times New Roman', serif; font-size: 16px; line-height: 1.6;">
                            {html_text.replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"An error occurred: {e}")

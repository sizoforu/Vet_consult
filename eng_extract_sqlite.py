from dotenv import load_dotenv
from PyPDF2 import PdfReader
import docx2txt
from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from langchain_core.prompts import PromptTemplate
import json
import streamlit as st
import os
from langchain.prompts.few_shot import FewShotPromptTemplate
import re
from langchain_core.messages import HumanMessage
import dotenv
import sqlite3
from docx import Document
from io import BytesIO
import datetime

# Load environment variables
load_dotenv()

# Define the example for few-shot learning
example = {
    "input_doc": "Dr. Smith conducted a consultation for Max, a 5-year-old Golden Retriever, on 2023-09-15. The owner, Jane Doe with the telephone number 15-9-1234-5678 reported vomiting, loss of appetite and limping on the right leg. A physical, neurological, and abdomen palpation was performed on Max.  the recomendation fro Dr Smith was to restrict the activity level of Max apply warm compress to hip area and consider starting of joints supplement.  The diagnostic from Dr; Smith was to an Xray",
    "entities_to_extract": ["date", "veterinarian_name", "pet_name", "pet_breed", "pet_age", "owner_name", "owner_phone", "symptoms", "examinations", "recomendations", "diagnostics"],
    "answer": """{{
        "date": "2023-09-15",
        "veterinarian_name": "Dr. Smith",
        "pet_name": "Max",
        "pet_breed": "Golden Retriever",
        "pet_age": 5,
        "owner_name": "Jane Doe",
        "owner_phone": "15-9-1234-5678",
        "symptoms": ["vomiting", "loss of appetite", "limping on the right leg"],
        "examinations": ["physical", "neurological", "abdomen palpation"],
        "recomendations": ["restrict activity level", "apply warm compress to hip area", "consider starting joint supplement"],
        "diagnostics": ["Xray"]
    }}"""
}

# Define the example template
example_template = """
User: Retrieve the following entities from the veterinary consultation document:
Document: {input_doc}
Entities: {entities_to_extract}
AI: The extracted entities are: {answer}
"""

example_prompt = PromptTemplate(
    input_variables=["input_doc", "entities_to_extract", "answer"],
    template=example_template
)

# Define the prefix and suffix for the few-shot prompt
prefix = """
You are an expert in veterinary consultation data extraction. Your task is to extract relevant entities from a given consultation document. 
Please pay attention to all the details in the following example and retrieve the requested entities accurately.
"""

suffix = """
User: Retrieve the requested entities from the veterinary consultation document.
Document: {input_doc}
Entities: {entities_to_extract}
AI: The extracted entities are:
"""

# Create the few-shot prompt template
few_shot_prompt_template = FewShotPromptTemplate(
    examples=[example],
    example_prompt=example_prompt,
    prefix=prefix,
    suffix=suffix,
    input_variables=["input_doc", "entities_to_extract"],
    example_separator="\n\n"
)

def save_consultation_docx(data, save_path='consultations'):
    """
    Save the DOCX file to a specified folder and return the BytesIO object
    """
    # Create the consultations directory if it doesn't exist
    os.makedirs(save_path, exist_ok=True)
    
    # Generate filename based on consultation date and pet name
    filename = f"consultation_{data.get('date', 'unknown_date')}_{data.get('pet_name', 'unknown_pet')}.docx"
    filename = re.sub(r'[^\w\-_\.]', '_', filename)  # Sanitize filename
    
    # Create the full file path
    file_path = os.path.join(os.getcwd(), save_path, filename)
    
    # Create the document
    doc = Document()
    
    # Add title
    doc.add_heading('Veterinary Consultation Report', 0)
    doc.add_paragraph(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Basic Information Section
    doc.add_heading('Basic Information', level=1)
    doc.add_paragraph(f"Date: {data.get('date', 'N/A')}")
    doc.add_paragraph(f"Veterinarian: {data.get('veterinarian_name', 'N/A')}")
    
    # Owner Information
    doc.add_heading('Owner Information', level=1)
    doc.add_paragraph(f"Name: {data.get('owner_name', 'N/A')}")
    doc.add_paragraph(f"Email: {data.get('owner_email', 'N/A')}")
    doc.add_paragraph(f"Phone: {data.get('owner_phone', 'N/A')}")
    
    # Pet Information
    doc.add_heading('Pet Information', level=1)
    doc.add_paragraph(f"Name: {data.get('pet_name', 'N/A')}")
    doc.add_paragraph(f"Breed: {data.get('pet_breed', 'N/A')}")
    doc.add_paragraph(f"Sex: {data.get('pet_sex', 'N/A')}")
    doc.add_paragraph(f"Age: {data.get('pet_age', 'N/A')}")
    
    # Consultation Details
    sections = {
        'Symptoms': data.get('symptoms', []),
        'Examinations': data.get('examinations', []),
        'Recommendations': data.get('recommendations', []),
        'Diagnostics': data.get('diagnostics', [])
    }
    
    for section_title, items in sections.items():
        doc.add_heading(section_title, level=1)
        if isinstance(items, list):
            for item in items:
                doc.add_paragraph(f"• {item}", style='List Bullet')
        else:
            doc.add_paragraph(f"• {items}", style='List Bullet')
    
    # Save the file to disk
    doc.save(file_path)
    
    # Also create a BytesIO object for the download button
    doc_io = BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return file_path, doc_io, filename

def insert_consultation(data):
    """
    Insert consultation data into the database with proper array handling
    """
    # Connect to SQLite database
    conn = sqlite3.connect('veterinary_consultations.db')
    cursor = conn.cursor()
    
    try:
        # Convert arrays to JSON strings for storage
        symptoms = json.dumps(data.get('symptoms', []))
        examinations = json.dumps(data.get('examinations', []))
        recommendations = json.dumps(data.get('recommendations', []))
        diagnostics = json.dumps(data.get('diagnostics', []))

        cursor.execute('''
        INSERT INTO consultations (
            date, 
            veterinarian_name, 
            owner_name, 
            owner_phone, 
            owner_email,
            pet_name, 
            pet_breed, 
            pet_sex,
            pet_age, 
            symptoms, 
            examinations, 
            recommendations, 
            diagnostics
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('date'),
            data.get('veterinarian_name'),
            data.get('owner_name'),
            data.get('owner_phone'),
            data.get('owner_email'),
            data.get('pet_name'),
            data.get('pet_breed'),
            data.get('pet_sex'),
            data.get('pet_age'),
            symptoms,
            examinations,
            recommendations,
            diagnostics
        ))

        conn.commit()
        st.success("💾 Data saved successfully to the database.")
    except Exception as e:
        st.error(f"❌ Error saving data to the database: {str(e)}")
    finally:
        conn.close()

def main():
    st.write("### 📋 Upload Consultation Document")
    
    status = st.empty()
    file = st.file_uploader("📎 Upload PDF or Word Doc", type=["pdf", "docx"])
    details = st.empty()
    
    # Create a session state for storing the processed data
    if 'consultation_data' not in st.session_state:
        st.session_state.consultation_data = None

    if file is not None:
        st.write(f"🔍 Processing: {file.name}")
        
        with st.spinner("🔄 Scanning document..."):
            try:
                text = ""
                if file.type == "application/pdf":
                    pdf_reader = PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text += docx2txt.process(file)
                
                # Set up the ChatOpenAI model
                groq_api_key = os.environ.get("GROQ_API_KEY")
                if not groq_api_key:
                    st.error("❌ GROQ_API_KEY not found in environment variables")
                    return

                llama3 = ChatOpenAI(
                    api_key=groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                    model="llama3-8b-8192",
                    temperature=0.1,
                )

                # Define the entities to extract
                entities_to_extract = ["date", "veterinarian_name", "owner_name", "owner_email", "owner_phone", 
                                     "pet_name", "pet_breed", "pet_sex", "pet_age", "symptoms", "examinations", 
                                     "recommendations", "diagnostics"]

                # Generate the prompt using the few-shot template
                prompt = few_shot_prompt_template.format(
                    input_doc=text,
                    entities_to_extract=entities_to_extract
                )

                response = llama3.invoke([HumanMessage(content=prompt)])
                response_content = response.content

                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(0)
                    data = json.loads(json_content)
                else:
                    raise ValueError("❌ No valid JSON object found in the response")

                # Store the data in session state
                st.session_state.consultation_data = data

                with details.container():
                    st.write("## 📊 Extracted Details")
                    
                    col1, col2 = st.columns(2)
                    
                    # Column 1: Basic Information
                    with col1:
                        st.subheader("📌 Basic Information")
                        st.write(f"📅 Date: {data.get('date', 'N/A')}")
                        st.write(f"👨‍⚕️ Veterinarian: {data.get('veterinarian_name', 'N/A')}")
                        st.write(f"👤 Owner: {data.get('owner_name', 'N/A')}")
                        st.write(f"📧 Email: {data.get('owner_email', 'N/A')}")
                        st.write(f"📱 Phone: {data.get('owner_phone', 'N/A')}")

                        st.subheader("🐾 Pet Information")
                        st.markdown(f"""\
                            * 🏷️ Name: {data.get('pet_name', 'N/A')}
                            * 🦮 Breed: {data.get('pet_breed', 'N/A')}
                            * ⚥ Sex: {data.get('pet_sex', 'N/A')}
                            * ⏳ Age: {data.get('pet_age', 'N/A')}
                        """)

                    # Column 2: Consultation Details
                    with col2:
                        section_icons = {
                            'symptoms': '🤒',
                            'examinations': '🔍',
                            'recommendations': '💡',
                            'diagnostics': '🔬'
                        }
                        
                        for section, icon in section_icons.items():
                            st.subheader(f"{icon} {section.capitalize()}")
                            items = data.get(section, [])
                            if isinstance(items, list):
                                for item in items:
                                    st.write(f"▫️ {item}")
                            else:
                                st.write(f"▫️ {items}")
                    
                    # Export section
                    if st.button("📥 Export Consultation"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Save locally
                            try:
                                file_path, doc_io, filename = save_consultation_docx(data)
                                st.success(f"✅ File saved locally to: {file_path}")
                            except Exception as e:
                                st.error(f"❌ Error saving file locally: {str(e)}")
                        
                        with col2:
                            # Provide download button as backup
                            st.download_button(
                                label="📄 Download DOCX",
                                data=doc_io.getvalue(),
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )

                status.success("✅ Consultation Scanned Successfully")
                
                # Insert the consultation data into the database
                insert_consultation(data)

            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                st.text("⚠️ Full traceback:")
                st.exception(e)

    else:
        st.info("📤 Please upload a file to begin scanning.")

# Database initialization
def init_db():
    conn = sqlite3.connect('veterinary_consultations.db')
    cursor = conn.cursor()

    # Create a table for storing consultation data with proper column types
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consultations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        veterinarian_name TEXT,
        owner_name TEXT,
        owner_phone TEXT,
        owner_email TEXT,
        pet_name TEXT,
        pet_breed TEXT,
        pet_sex TEXT,
        pet_age INTEGER,
        symptoms TEXT,
        examinations TEXT,
        recommendations TEXT,
        diagnostics TEXT
    )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    main()
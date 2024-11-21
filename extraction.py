from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date
from enum import Enum
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
import streamlit as st
import json
import re
from datetime import datetime
import docx2txt
from PyPDF2 import PdfReader
import os
from dotenv import load_dotenv
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor
import io
import sqlite3
from enum import Enum

# Load environment variables
load_dotenv()



class DiagnosticPriority(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'

class Diagnostic(BaseModel):
    diagnosis: str
    details: str = ''
    priority: DiagnosticPriority



class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Examination(BaseModel):
    type: str = Field(..., description="Types of examination performed")
    #type: List[str] = Field(..., description="Type of examination performed")
    findings: List[str] = Field(..., description="List of findings from the examination")
    region: Optional[str] = Field(None, description="Body region examined")
    notes: Optional[str] = Field(None, description="Additional examination notes")

class Recommendation(BaseModel):
    type: str = Field(..., description="Types of recommendation including medication")
    details: str = Field(..., description="Specific instructions")
    duration: Optional[str] = Field(None, description="Time period if applicable")
    notes: Optional[str] = Field(None, description="Additional information")

class Diagnostic(BaseModel):
    type: str = Field(..., description="Types of diagnostic")
    test: str = Field(default="pending", description="Name of the specific test")  # Fixed Field definition
    region: Optional[str] = Field(None, description="Body region if applicable")
    priority: Priority = Field(..., description="Urgency level")
    reason: str = Field(..., description="Reason for the diagnostic")

class VeterinaryConsultation(BaseModel):
    consultation_date: date = Field(..., description="Consultation date in YYYY-MM-DD format")
    veterinarian_name: str = Field(..., description="Veterinarian's name")
    pet_name: str = Field(..., description="Pet's name")
    pet_breed: str = Field(..., description="Pet's breed")
    pet_age: float = Field(..., ge=0, description="Pet's age in years")
    owner_name: str = Field(..., description="Pet owner's name")
    owner_phone: str = Field(..., description="Contact phone number")
    symptoms: List[str] = Field(..., description="List of observed symptoms")
    examinations: List[Examination] = Field(..., description="List of examinations performed")
    recommendations: List[Recommendation] = Field(..., description="List of recommendations including medications")
    diagnostics: List[Diagnostic] = Field(..., description="List of diagnostics")

    @field_validator('owner_phone')
    def validate_phone(cls, v):
        # Remove any non-digit characters except leading '+'
        cleaned_phone = '+' + ''.join(filter(str.isdigit, v)) if v.startswith('+') else ''.join(filter(str.isdigit, v))
        
        # Check if the cleaned number matches the pattern
        if not re.match(r'^\+?1?\d{9,15}$', cleaned_phone):
            raise ValueError('Invalid phone number format')
        return cleaned_phone

    @field_validator('diagnostics')
    def validate_diagnostics(cls, v):
        # Ensure each diagnostic has a test value
        for diagnostic in v:
            if diagnostic.test is None:
                diagnostic.test = "pending"  # Set default value if None
        return v

class VetDatabaseManager:
    def __init__(self, db_name='vet_consult.db'):
        self.db_name = db_name
        self.create_database()

    def create_database(self):
        """Create the veterinary consultation database and table."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_date DATE NOT NULL,
            veterinarian_name TEXT NOT NULL,
            pet_name TEXT NOT NULL,
            pet_breed TEXT NOT NULL,
            pet_age REAL NOT NULL,
            owner_name TEXT NOT NULL,
            owner_phone TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            examinations TEXT NOT NULL,
            recommendations TEXT NOT NULL,
            diagnostics TEXT NOT NULL
        )
        ''')
        
        conn.commit()
        conn.close()

    def _format_examination(self, exam):
        """Format examination data in a human-readable format."""
        parts = [f"Type: {exam.type}"]
        if exam.findings:
            parts.append("Findings:")
            parts.extend([f"  - {finding}" for finding in exam.findings])
        if exam.region:
            parts.append(f"Region: {exam.region}")
        if exam.notes:
            parts.append(f"Notes: {exam.notes}")
        return "\n".join(parts)

    def _format_recommendation(self, rec):
        """Format recommendation data in a human-readable format."""
        parts = [f"Type: {rec.type}"]
        parts.append(f"Details: {rec.details}")
        if rec.duration:
            parts.append(f"Duration: {rec.duration}")
        if rec.notes:
            parts.append(f"Notes: {rec.notes}")
        return "\n".join(parts)

    def _format_diagnostic(self, diag):
        """Format diagnostic data in a human-readable format."""
        parts = [f"Type: {diag.type}"]
        parts.append(f"Test: {diag.test}")
        parts.append(f"Priority: {diag.priority}")
        parts.append(f"Reason: {diag.reason}")
        if diag.region:
            parts.append(f"Region: {diag.region}")
        return "\n".join(parts)

    def _parse_examination(self, text):
        """Parse examination text back into a structured format."""
        lines = text.split('\n')
        exam_dict = {}
        findings = []
        current_section = None
        
        for line in lines:
            if line.startswith('Type: '):
                exam_dict['type'] = line.replace('Type: ', '')
            elif line.startswith('Region: '):
                exam_dict['region'] = line.replace('Region: ', '')
            elif line.startswith('Notes: '):
                exam_dict['notes'] = line.replace('Notes: ', '')
            elif line == 'Findings:':
                current_section = 'findings'
            elif line.startswith('  - ') and current_section == 'findings':
                findings.append(line.replace('  - ', ''))
        
        exam_dict['findings'] = findings
        return Examination(**exam_dict)



    def _parse_recommendation(self, text):
        """Parse recommendation text back into a structured format."""
        # If no text, return an empty Recommendation
        if not text:
            return Recommendation(type='', details='')

        lines = text.split('\n')
        rec_dict = {}
        
        for line in lines:
            if line.startswith('Type: '):
                rec_dict['type'] = line.replace('Type: ', '').strip()
            elif line.startswith('Details: '):
                rec_dict['details'] = line.replace('Details: ', '').strip()
            elif line.startswith('Duration: '):
                rec_dict['duration'] = line.replace('Duration: ', '').strip()
            elif line.startswith('Notes: '):
                rec_dict['notes'] = line.replace('Notes:', '').strip()
            
                # Ensure type is always present
            if 'type' not in rec_dict:
                rec_dict['type'] = ''
        
            # Provide a default details if not present
            if 'details' not in rec_dict:
                rec_dict['details'] = ''
        
            return Recommendation(**rec_dict)
            
        
    def _parse_diagnostic(self, diag_text):
        """Parse diagnostic text into a Diagnostic object."""
        # If no text, return an empty Diagnostic
        if not diag_text:
            return Diagnostic()

        lines = diag_text.split('\n')
        diag_dict = {}
        
        for line in lines:
            if line.startswith('Type: '):
                diag_dict['type'] = line.replace('Type: ', '').strip()
            elif line.startswith('Test: '):
                diag_dict['test'] = line.replace('Test: ', '').strip()
            elif line.startswith('Priority: '):
                priority_value = line.replace('Priority: ', '').strip().lower()
                # Convert Priority.LOW to 'low' if needed
                if priority_value.startswith('priority.'):
                    priority_value = priority_value.split('.')[-1].lower()
                
                # Only set priority if it's a valid enum value
                if priority_value in ['low', 'medium', 'high', 'urgent']:
                    diag_dict['priority'] = priority_value
            elif line.startswith('Reason: '):
                diag_dict['reason'] = line.replace('Reason: ', '').strip()
            elif line.startswith('Region: '):
                diag_dict['region'] = line.replace('Region: ', '').strip()
        
        return Diagnostic(**diag_dict)

    
    def add_consultation(self, consultation: VeterinaryConsultation):
        """Add a new consultation to the database with human-readable format."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Format complex fields in human-readable format
        formatted_symptoms = "\n- " + "\n- ".join(consultation.symptoms)
        formatted_examinations = "\n\n".join(self._format_examination(exam) for exam in consultation.examinations)
        formatted_recommendations = "\n\n".join(self._format_recommendation(rec) for rec in consultation.recommendations)
        formatted_diagnostics = "\n\n".join(self._format_diagnostic(diag) for diag in consultation.diagnostics)
        
        cursor.execute('''
        INSERT INTO consultations (
            consultation_date,
            veterinarian_name,
            pet_name,
            pet_breed,
            pet_age,
            owner_name,
            owner_phone,
            symptoms,
            examinations,
            recommendations,
            diagnostics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            consultation.consultation_date.isoformat(),
            consultation.veterinarian_name,
            consultation.pet_name,
            consultation.pet_breed,
            consultation.pet_age,
            consultation.owner_name,
            consultation.owner_phone,
            formatted_symptoms,
            formatted_examinations,
            formatted_recommendations,
            formatted_diagnostics
        ))
        
        consultation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return consultation_id
    
    def get_consultation(self, consultation_id: int) -> VeterinaryConsultation:
        """Retrieve a specific consultation from the database."""
        conn = sqlite3.connect(self.db_name)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM consultations WHERE id = ?', (consultation_id,))
            row = cursor.fetchone()
        
            if row:
                    columns = [description[0] for description in cursor.description]
                    consultation_dict = dict(zip(columns, row))
            
                    # Parse the human-readable format back into structured data
                    consultation_dict['symptoms'] = [s.strip('- ') for s in consultation_dict['symptoms'].split('\n') if s.strip('- ')]
                    consultation_dict['examinations'] = [
                    self._parse_examination(exam_text)
                for exam_text in consultation_dict['examinations'].split('\n\n')
                if exam_text.strip()
                    ]
                    consultation_dict['recommendations'] = [
                    self._parse_recommendation(rec_text)
                for rec_text in consultation_dict['recommendations'].split('\n\n')
                if rec_text.strip()
                    ]
                    consultation_dict['diagnostics'] = [
                    self._parse_diagnostic(diag_text)
                for diag_text in consultation_dict['diagnostics'].split('\n\n')
                if diag_text.strip()
                    ]
                    # Convert date string back to date object
                    consultation_dict['consultation_date'] = date.fromisoformat(consultation_dict['consultation_date'])        
            return VeterinaryConsultation(**consultation_dict)       
            return None
        finally:
            conn.close()
    
    def update_consultation(self, consultation_id: int, consultation: VeterinaryConsultation):
        """Update an existing consultation in the database with human-readable format."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            # Format complex fields in human-readable format
            formatted_symptoms = "\n- " + "\n- ".join(consultation.symptoms) if consultation.symptoms else ""
            
            # Handle potentially empty lists
            formatted_examinations = "\n\n".join(
                self._format_examination(exam) for exam in (consultation.examinations or [])
            )
            
            formatted_recommendations = "\n\n".join(
                self._format_recommendation(rec) for rec in (consultation.recommendations or [])
            )
            
            formatted_diagnostics = "\n\n".join(
                self._format_diagnostic(diag) for diag in (consultation.diagnostics or [])
            )
            
            cursor.execute('''
            UPDATE consultations SET
                consultation_date = ?,
                veterinarian_name = ?,
                pet_name = ?,
                pet_breed = ?,
                pet_age = ?,
                owner_name = ?,
                owner_phone = ?,
                symptoms = ?,
                examinations = ?,
                recommendations = ?,
                diagnostics = ?
            WHERE id = ?
            ''', (
                consultation.consultation_date.isoformat(),
                consultation.veterinarian_name,
                consultation.pet_name,
                consultation.pet_breed,
                consultation.pet_age,
                consultation.owner_name,
                consultation.owner_phone,
                formatted_symptoms,
                formatted_examinations,
                formatted_recommendations,
                formatted_diagnostics,
                consultation_id
            ))
            
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    
    def get_all_consultations_summary(self):
        """Get a summary of all consultations for display in a selection widget."""
        conn = sqlite3.connect(self.db_name)
        try:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, consultation_date, pet_name, owner_name
            FROM consultations
            ORDER BY consultation_date DESC
            ''')
            consultations = cursor.fetchall()
            return [{"id": c[0], "date": c[1], "pet": c[2], "owner": c[3]} for c in consultations]
        except Exception as e:
            print(f"Error retrieving consultations summary: {e}")
            return []
        finally:
            conn.close()  
            
              
    
    def get_consultation(self, consultation_id: int) -> VeterinaryConsultation:
        """Retrieve a specific consultation from the database."""
        conn = sqlite3.connect(self.db_name)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM consultations WHERE id = ?', (consultation_id,))
            row = cursor.fetchone()
        
            if row:
                columns = [description[0] for description in cursor.description]
                consultation_dict = dict(zip(columns, row))
            
                # Parse symptoms from human-readable format
            if consultation_dict['symptoms']:
                consultation_dict['symptoms'] = [
                    s.strip('- ') for s in consultation_dict['symptoms'].split('\n') 
                    if s.strip('- ')
                ]
            
            # Parse examinations from human-readable format
            if consultation_dict['examinations']:
                consultation_dict['examinations'] = [
                    self._parse_examination(exam_text)
                    for exam_text in consultation_dict['examinations'].split('\n\n')
                    if exam_text.strip()
                ]
            
            # Parse recommendations from human-readable format
            if consultation_dict['recommendations']:
                consultation_dict['recommendations'] = [
                    self._parse_recommendation(rec_text)
                    for rec_text in consultation_dict['recommendations'].split('\n\n')
                    if rec_text.strip()
                ]
            
            # Parse diagnostics from human-readable format
            if consultation_dict['diagnostics']:
                consultation_dict['diagnostics'] = [
                    self._parse_diagnostic(diag_text)
                    for diag_text in consultation_dict['diagnostics'].split('\n\n')
                    if diag_text.strip()
                ]            
                # Convert date string back to date object
                consultation_dict['consultation_date'] = date.fromisoformat(consultation_dict['consultation_date'])
            
                return VeterinaryConsultation(**consultation_dict) 
            return None   
        finally:
            conn.close()


    def get_all_consultations(self) -> List[VeterinaryConsultation]:
        """Retrieve all consultations from the database."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM consultations')
        rows = cursor.fetchall()
        
        consultations = []
        columns = [description[0] for description in cursor.description]
        
        for row in rows:
            consultation_dict = dict(zip(columns, row))
            
            # Parse JSON strings back to Python objects
            consultation_dict['symptoms'] = json.loads(consultation_dict['symptoms'])
            consultation_dict['examinations'] = json.loads(consultation_dict['examinations'])
            consultation_dict['recommendations'] = json.loads(consultation_dict['recommendations'])
            consultation_dict['diagnostics'] = json.loads(consultation_dict['diagnostics'])
            
            # Convert date string back to date object
            consultation_dict['consultation_date'] = date.fromisoformat(consultation_dict['consultation_date'])
            
            consultations.append(VeterinaryConsultation(**consultation_dict))
        
        conn.close()
        return consultations


def display_consultation_data(data):
    """Display the extracted consultation data in a structured format."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📌 Basic Information")
        st.write(f"📅 Date: {data.consultation_date}")
        st.write(f"👨‍⚕️ Veterinarian: {data.veterinarian_name}")
        
        st.subheader("👤 Owner Information")
        st.write(f"Name: {data.owner_name}")
        st.write(f"Phone: {data.owner_phone}")

    with col2:
        st.subheader("🐾 Pet Information")
        st.write(f"Name: {data.pet_name}")
        st.write(f"Breed: {data.pet_breed}")
        st.write(f"Age: {data.pet_age} years")
        
        st.subheader("🤒 Symptoms")
        for symptom in data.symptoms:
            st.write(f"• {symptom}")

    with col3:
        st.subheader("🔍 Examinations")
        for exam in data.examinations:
            with st.expander(f"{exam.type}"):
                st.write("Findings:")
                for finding in exam.findings:
                    st.write(f"• {finding}")
                if exam.region:
                    st.write(f"Region: {exam.region}")
                if exam.notes:
                    st.write(f"Notes: {exam.notes}")

        st.subheader("💡 Recommendations")
        for rec in data.recommendations:
            with st.expander(f"{rec.type}"):
                st.write(f"Details: {rec.details}")
                if rec.duration:
                    st.write(f"Duration: {rec.duration}")
                if rec.notes:
                    st.write(f"Notes: {rec.notes}")

        st.subheader("🔬 Diagnostics")
        for diag in data.diagnostics:
            with st.expander(f"{diag.type}"):
                st.write(f"Test: {diag.test}")
                st.write(f"Priority: {diag.priority}")
                st.write(f"Reason: {diag.reason}")
                if diag.region:
                    st.write(f"Region: {diag.region}")

class VeterinaryConsultationExtractor:
    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=VeterinaryConsultation)
        self.prompt_template = self._create_prompt_template()
        self.llm = self._initialize_llm()

    def _create_prompt_template(self):
        template = """
        Extract strucure data from veterinary consultations from the following text and format it according to these requirements:

        {format_instructions}

        Important guidelines:
        1. Extract exact dates, names, and numbers when present
        2. Categorize symptoms clearly and concisely
        3. Categorize types of examinations and their findings accordingly to the text
        4. Categorize recommendations with medications and clear timeframes when specified
        5. Assign appropriate priority levels to diagnostics

        Text: {consultation_text}

        Please provide a complete and detailed extraction following the exact schema specified.
        Use the current date if no specific date is mentioned.
        Do not make assumptions for required fields if the information is not explicitly stated.
        """
        return PromptTemplate(
            template=template,
            input_variables=["consultation_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

    def _initialize_llm(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        return ChatOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            model="llama3-8b-8192",
            #model="mixtral-8x7b-32768",
            #model="llama3-70b-8192",
            #model="gemma2-9b-it",
            temperature=0.1
        )

    def extract_text_from_file(self, file):
        """Extract text from uploaded PDF or DOCX file."""
        try:
            if file.type == "application/pdf":
                pdf_reader = PdfReader(file)
                return ' '.join(page.extract_text() for page in pdf_reader.pages)
            else:  # DOCX
                return docx2txt.process(file)
        except Exception as e:
            raise Exception(f"Error extracting text from file: {str(e)}")

    def process_consultation(self, text):
        """Process consultation text and extract structured information."""
        try:
            # Generate formatted prompt
            formatted_prompt = self.prompt_template.format_prompt(
                consultation_text=text
            ).to_string()
            
            # Get response from LLM
            response = self.llm.invoke(formatted_prompt)
            
            try:
                # Try to parse JSON from the response
                json_str = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_str:
                    consultation_data = json.loads(json_str.group())
                    # Parse the cleaned JSON into the Pydantic model
                    return self.parser.parse(json.dumps(consultation_data))
                else:
                    raise ValueError("No JSON found in response")
            except json.JSONDecodeError as e:
                st.error(f"JSON parsing error: {str(e)}")
                return None
            
        except Exception as e:
            st.error(f"Error processing consultation: {str(e)}")
            return None

def create_consultation_docx(consultation_data):
        """
        Create a formatted DOCX document from consultation data.
        Returns a BytesIO object containing the document.
        """
        doc = Document()
    
        # Set up title
        title = doc.add_heading('Veterinary Consultation Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
        # Add basic information section
        doc.add_heading('Basic Information', level=1)
        basic_info = doc.add_paragraph()
        basic_info.add_run('Date: ').bold = True
        basic_info.add_run(f"{consultation_data.consultation_date}\n")
        basic_info.add_run('Veterinarian: ').bold = True
        basic_info.add_run(f"{consultation_data.veterinarian_name}\n")
    
        # Add owner information
        doc.add_heading('Owner Information', level=1)
        owner_info = doc.add_paragraph()
        owner_info.add_run('Name: ').bold = True
        owner_info.add_run(f"{consultation_data.owner_name}\n")
        owner_info.add_run('Phone: ').bold = True
        owner_info.add_run(f"{consultation_data.owner_phone}\n")
    
        # Add pet information
        doc.add_heading('Pet Information', level=1)
        pet_info = doc.add_paragraph()
        pet_info.add_run('Name: ').bold = True
        pet_info.add_run(f"{consultation_data.pet_name}\n")
        pet_info.add_run('Breed: ').bold = True
        pet_info.add_run(f"{consultation_data.pet_breed}\n")
        pet_info.add_run('Age: ').bold = True
        pet_info.add_run(f"{consultation_data.pet_age} years\n")
    
        # Add symptoms
        doc.add_heading('Symptoms', level=1)
        for symptom in consultation_data.symptoms:
            doc.add_paragraph(symptom, style='List Bullet')
    
        # Add examinations
        doc.add_heading('Examinations', level=1)
        for exam in consultation_data.examinations:
            p = doc.add_paragraph()
            p.add_run(f"Type: {exam.type}\n").bold = True
            p.add_run('Findings:\n')
        for finding in exam.findings:
            doc.add_paragraph(finding, style='List Bullet')
        if exam.region:
            p.add_run(f"Region: {exam.region}\n")
        if exam.notes:
            p.add_run(f"Notes: {exam.notes}\n")
        doc.add_paragraph()  # Add spacing between examinations
    
        # Add recommendations
        doc.add_heading('Recommendations', level=1)
        for rec in consultation_data.recommendations:
            p = doc.add_paragraph()
            p.add_run(f"Type: {rec.type}\n").bold = True
            p.add_run(f"Details: {rec.details}\n")
        if rec.duration:
            p.add_run(f"Duration: {rec.duration}\n")
        if rec.notes:
            p.add_run(f"Notes: {rec.notes}\n")
        doc.add_paragraph()  # Add spacing between recommendations
    
        # Add diagnostics
        doc.add_heading('Diagnostics', level=1)
        for diag in consultation_data.diagnostics:
            p = doc.add_paragraph()
            p.add_run(f"Type: {diag.type}\n").bold = True
            p.add_run(f"Test: {diag.test}\n")
            # Add priority with color coding
            priority_run = p.add_run(f"Priority: {diag.priority}\n")
        if diag.priority == "urgent":
            priority_run.font.color.rgb = RGBColor(255, 0, 0)  # Red
        elif diag.priority == "high":
            priority_run.font.color.rgb = RGBColor(255, 165, 0)  # Orange
        p.add_run(f"Reason: {diag.reason}\n")
        if diag.region:
            p.add_run(f"Region: {diag.region}\n")
        doc.add_paragraph()  # Add spacing between diagnostics
    
        # Save to BytesIO object
        docx_file = io.BytesIO()
        doc.save(docx_file)
        docx_file.seek(0)
    
        return docx_file


def create_edit_form(consultation_data):
    """
    Create a form for editing the consultation data.
    Returns the updated consultation data or None if the form is not submitted.
    """
    with st.form("edit_consultation_form"):
        st.subheader("Edit Consultation")

        if consultation_data is None:
            st.info("No consultation data available to edit.")
            return None

        # Basic information
        col1, col2 = st.columns(2)
        
        with col1:
            consultation_date = st.date_input("Consultation Date", value=consultation_data.consultation_date)
            veterinarian_name = st.text_input("Veterinarian Name", value=consultation_data.veterinarian_name)
            
            # Owner information
            st.subheader("Owner Information")
            owner_name = st.text_input("Owner Name", value=consultation_data.owner_name)
            owner_phone = st.text_input("Owner Phone", value=consultation_data.owner_phone)

        with col2:
            # Pet information
            st.subheader("Pet Information")
            pet_name = st.text_input("Pet Name", value=consultation_data.pet_name)
            pet_breed = st.text_input("Pet Breed", value=consultation_data.pet_breed)
            pet_age = st.number_input("Pet Age", value=consultation_data.pet_age, min_value=0.0, step=0.1)

        # Symptoms
        st.subheader("Symptoms")
        symptoms = st.text_area("Symptoms (comma-separated)", value=", ".join(consultation_data.symptoms))

        # Examinations
        st.subheader("Examinations")
        examinations = []
        for i, exam in enumerate(consultation_data.examinations):
            with st.expander(f"Examination {i+1}", expanded=True):
                exam_type = st.text_input("Type", value=exam.type, key=f"exam_type_{i}")
                findings = st.text_area("Findings (comma-separated)", 
                                      value=", ".join(exam.findings), 
                                      key=f"exam_findings_{i}")
                region = st.text_input("Region", value=exam.region or "", key=f"exam_region_{i}")
                notes = st.text_area("Notes", value=exam.notes or "", key=f"exam_notes_{i}")
                examinations.append({
                    'type': exam_type,
                    'findings': findings,
                    'region': region,
                    'notes': notes
                })

        # Recommendations
        st.subheader("Recommendations")
        recommendations = []
        for i, rec in enumerate(consultation_data.recommendations):
            with st.expander(f"Recommendation {i+1}", expanded=True):
                rec_type = st.text_input("Type", value=rec.type, key=f"rec_type_{i}")
                details = st.text_area("Details", value=rec.details, key=f"rec_details_{i}")
                duration = st.text_input("Duration", value=rec.duration or "", key=f"rec_duration_{i}")
                notes = st.text_area("Notes", value=rec.notes or "", key=f"rec_notes_{i}")
                recommendations.append({
                    'type': rec_type,
                    'details': details,
                    'duration': duration,
                    'notes': notes
                })

        # Diagnostics
        st.subheader("Diagnostics")
        diagnostics = []
        for i, diag in enumerate(consultation_data.diagnostics):
            with st.expander(f"Diagnostic {i+1}", expanded=True):
                diag_type = st.text_input("Type", value=diag.type, key=f"diag_type_{i}")
                test = st.text_input("Test", value=diag.test, key=f"diag_test_{i}")
                priority = st.selectbox(
                    "Priority",
                    options=[p.value for p in Priority],
                    index=[p.value for p in Priority].index(diag.priority),
                    key=f"diag_priority_{i}"
                )
                reason = st.text_area("Reason", value=diag.reason, key=f"diag_reason_{i}")
                region = st.text_input("Region", value=diag.region or "", key=f"diag_region_{i}")
                diagnostics.append({
                    'type': diag_type,
                    'test': test,
                    'priority': priority,
                    'reason': reason,
                    'region': region
                })

        submit_button = st.form_submit_button("Save Changes")
        
        if submit_button:
            try:
                # Convert the form data back to a VeterinaryConsultation object
                return VeterinaryConsultation(
                    consultation_date=consultation_date,
                    veterinarian_name=veterinarian_name,
                    pet_name=pet_name,
                    pet_breed=pet_breed,
                    pet_age=pet_age,
                    owner_name=owner_name,
                    owner_phone=owner_phone,
                    symptoms=[s.strip() for s in symptoms.split(",") if s.strip()],
                    examinations=[
                        Examination(
                            type=e['type'],
                            findings=[f.strip() for f in e['findings'].split(",") if f.strip()],
                            region=e['region'] if e['region'] else None,
                            notes=e['notes'] if e['notes'] else None
                        ) for e in examinations
                    ],
                    recommendations=[
                        Recommendation(
                            type=r['type'],
                            details=r['details'],
                            duration=r['duration'] if r['duration'] else None,
                            notes=r['notes'] if r['notes'] else None
                        ) for r in recommendations
                    ],
                    diagnostics=[
                        Diagnostic(
                            type=d['type'],
                            test=d['test'],
                            priority=Priority(d['priority']),
                            reason=d['reason'],
                            region=d['region'] if d['region'] else None
                        ) for d in diagnostics
                    ]
                )
            except Exception as e:
                st.error(f"Error saving changes: {str(e)}")
                return None
        return None
    
    
def edit_consultation():
    """Function to handle consultation editing"""
    # Initialize database manager
    db_manager = VetDatabaseManager()

    # Add consultation selector
    consultations = db_manager.get_all_consultations_summary()

    if not consultations:
        st.info("No consultations found in the database.")
        return

    # Create selection box for consultations
    selected_consultation = st.selectbox(
        "Select Consultation to Edit",
        options=consultations,
        format_func=lambda x: f"{x['date']} - {x['pet']} ({x['owner']})"
    )

    if selected_consultation:
        # Load the selected consultation
        consultation_data = db_manager.get_consultation(selected_consultation['id'])
        
        if consultation_data:
            # Create and handle the edit form
            updated_data = create_edit_form(consultation_data)
            
            if updated_data:
                try:
                    success = db_manager.update_consultation(
                        selected_consultation['id'],
                        updated_data
                    )
                    if success:
                        st.success("✅ Changes saved successfully!")

                        # Create updated DOCX file
                        docx_file = create_consultation_docx(updated_data)

                        # Add download button for updated report
                        st.download_button(
                            label="📥 Download Updated DOCX Report",
                            data=docx_file.getvalue(),
                            file_name=f"consultation_{updated_data.consultation_date}_{updated_data.pet_name}_updated.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        st.error("Failed to update consultation. Please try again.")
                except Exception as e:
                    st.error(f"Error saving changes: {str(e)}")
        else:
            st.error("Failed to load consultation data. Please try again.")


def main():
    #st.set_page_config(page_title="Veterinary Consultation Scanner", layout="wide")

    # Initialize session state
    if 'consultation_data' not in st.session_state:
        st.session_state.consultation_data = None
    if 'consultation_id' not in st.session_state:
        st.session_state.consultation_id = None

    # Create tabs
    scan_tab, edit_tab = st.tabs(["📄 Scan Document", "✏️ Edit Consultation"])

    with scan_tab:
        st.title("📄 Scan Veterinary Consultation")
        process_uploaded_file()

    with edit_tab:
        st.title("✏️ Edit Consultation Data")
        edit_consultation()

def process_uploaded_file():
    # File upload
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])
    
    
    if uploaded_file is not None:
        # Extract text from the uploaded file
        extractor = VeterinaryConsultationExtractor()
        try:
            with st.spinner("Processing document..."):
                consultation_text = extractor.extract_text_from_file(uploaded_file)
                consultation_data = extractor.process_consultation(consultation_text)
    
            if consultation_data:
                # Display the consultation data
                display_consultation_data(consultation_data)

                # Initialize database manager and save consultation
                db_manager = VetDatabaseManager()
                try:
                    consultation_id = db_manager.add_consultation(consultation_data)
                    st.session_state.consultation_id = consultation_id  # Store the ID
                    st.success("✅ Consultation saved to database!")
                except Exception as e:
                    st.error(f"Error saving to database: {str(e)}")

                # Create DOCX file
                docx_file = create_consultation_docx(consultation_data)

                # Add download button for the report
                st.download_button(
                    label="📥 Download DOCX Report",
                    data=docx_file.getvalue(),
                    file_name=f"consultation_{consultation_data.consultation_date}_{consultation_data.pet_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.exception(e)

def edit_consultation():
    """Function to handle consultation editing"""
    # Initialize database manager
    db_manager = VetDatabaseManager()

    # Initialize session state variables if they don't exist
    if 'previous_consultation_id' not in st.session_state:
        st.session_state.previous_consultation_id = None
    if 'consultation_data' not in st.session_state:
        st.session_state.consultation_data = None
    if 'consultation_id' not in st.session_state:
        st.session_state.consultation_id = None

    # Add consultation selector
    consultations = db_manager.get_all_consultations_summary()

    if not consultations:
        st.info("No consultations found in the database.")
        return

    def on_consultation_select():
        """Callback function for when a new consultation is selected"""
        selected = st.session_state.consultation_selector
        if selected and selected['id'] != st.session_state.previous_consultation_id:
            consultation_data = db_manager.get_consultation(selected['id'])
            st.session_state.consultation_data = consultation_data
            st.session_state.consultation_id = selected['id']
            st.session_state.previous_consultation_id = selected['id']

    # Create selection box for consultations with callback
    selected_consultation = st.selectbox(
        "Select Consultation to Edit",
        options=consultations,
        format_func=lambda x: f"{x['date']} - {x['pet']} ({x['owner']})",
        key="consultation_selector",
        on_change=on_consultation_select
    )

    if st.session_state.consultation_data:
        # Create edit form with current consultation data
        updated_data = create_edit_form(st.session_state.consultation_data)  # Pass the consultation_data argument

        if updated_data:
            # Update database
            try:
                success = db_manager.update_consultation(
                    st.session_state.consultation_id,
                    updated_data
                )
                if success:
                    st.success("✅ Changes saved successfully!")
                    st.session_state.consultation_data = updated_data

                    # Create updated DOCX file
                    docx_file = create_consultation_docx(updated_data)

                    # Add download button for updated report
                    st.download_button(
                        label="📥 Download Updated DOCX Report",
                        data=docx_file.getvalue(),
                        file_name=f"consultation_{updated_data.consultation_date}_{updated_data.pet_name}_updated.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error("No consultation was updated. Please check the consultation ID.")
            except Exception as e:
                st.error(f"Error saving changes: {str(e)}")


if __name__ == "__main__":
    main() 
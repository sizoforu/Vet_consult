import streamlit as st
import os
import base64
from pydub import AudioSegment
from openai import OpenAI
from dotenv import load_dotenv
from docx import Document
from io import BytesIO
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import eng_extract_sqlite  # Import the document scanner module
import eng_editing  # Import the editing module

# App configuration - THIS MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(
    layout="wide",
    page_title="Veterinary Medical App",
    page_icon="🐾"
)

# Load environment variables
#load_dotenv()

class VetTranscriptionApp:
    def __init__(self):
        self.groq_client = OpenAI(
            api_key=st.secrets["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1"
        )
        

    def generate_pdf(self, transcription):
        """Generate a PDF document from the transcription."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        custom_style = ParagraphStyle(
            'CustomStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceBefore=12,
            spaceAfter=12
        )

        story = []
        title = Paragraph("Veterinary Transcription Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        section_title = Paragraph("Transcription:", styles['Heading1'])
        story.append(section_title)
        story.append(Spacer(1, 12))
        
        paragraphs = transcription.split('\n\n')
        for para in paragraphs:
            p = Paragraph(para, custom_style)
            story.append(p)
            story.append(Spacer(1, 6))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_docx(transcription, analysis=None):
        """Generate a DOCX document from the transcription and analysis."""
        doc = Document()
        doc.add_heading('Veterinary Transcription Report', 0)
        
        doc.add_heading('Raw Transcription', level=1)
        doc.add_paragraph(transcription)
        
        if analysis:
            doc.add_heading('Analysis', level=1)
            doc.add_paragraph(analysis)
        
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio

    @staticmethod
    def get_download_link(bio, filename):
        """Generate a download link for the document."""
        b64 = base64.b64encode(bio.read()).decode()
        file_ext = filename.split('.')[-1].lower()
        
        mime_type = 'application/pdf' if file_ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        return f'<a href="data:{mime_type};base64,{b64}" download="{filename}">Download {filename}</a>'

    @staticmethod
    def audio_to_base64(file_path):
        """Convert audio file to base64 string."""
        with open(file_path, "rb") as audio_file:
            return base64.b64encode(audio_file.read()).decode()

    def transcribe_audio(self, audio_file_path):
        """Transcribe audio using Groq API."""
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.groq_client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio_file,
                    response_format="text"
                )
            return transcript
        except Exception as e:
            st.error(f"Error during transcription: {str(e)}")
            return None

def show_transcription_page():
    """Display the transcription page content"""
    st.title("🎙️ Audio Transcription")
    st.markdown("""
        Upload an audio recording of your veterinary consultation to generate a transcription report.
    """)
    
    app = VetTranscriptionApp()
    
    uploaded_file = st.file_uploader("Upload an MP3 file", type=["mp3"])
    col1, col2 = st.columns(2)

    if uploaded_file is not None:
        with col1:
            st.subheader("📂 Uploaded Audio File")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                temp_file_path = tmp_file.name

            base64_audio = app.audio_to_base64(temp_file_path)
            audio_html = f"""
                <audio controls style="width: 100%">
                    <source src="data:audio/mp3;base64,{base64_audio}" type="audio/mp3">
                    Your browser does not support the audio element.
                </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)

            if st.button("🎯 Generate Transcription"):
                with st.spinner("Transcribing audio..."):
                    transcript = app.transcribe_audio(temp_file_path)
                    
                    if transcript:
                        with col2:
                            st.subheader("📝 Transcription Result")
                            st.success("Transcription completed successfully!")
                            st.text_area("Raw Transcription", transcript, height=300)

                            pdf_bio = app.generate_pdf(transcript)
                            doc_bio = app.generate_docx(transcript)

                            st.markdown("### Download Options")
                            st.markdown(
                                app.get_download_link(pdf_bio, "veterinary_report.pdf"),
                                unsafe_allow_html=True
                            )
                            st.markdown(
                                app.get_download_link(doc_bio, "veterinary_report.docx"),
                                unsafe_allow_html=True
                            )

        os.unlink(temp_file_path)

def main():
    # Create a custom CSS style for the dropdown
    st.markdown("""
        <style>
        .stSelectbox {
            width: 200px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Add sidebar logo/title
    st.sidebar.title("🐾 Veterinary Medical App")
    
    # Update dropdown with the new option
    page = st.sidebar.selectbox(
        "Choose a Module",
        ["Audio Transcription", "Document Scanner", "Consultation Editor"],
        format_func=lambda x: {
            "Audio Transcription": "📝 Audio Transcription",
            "Document Scanner": "🏥 Document Scanner",
            "Consultation Editor": "✏️ Consultation Editor"
        }[x]
    )

    if page == "Audio Transcription":
        show_transcription_page()
    elif page == "Document Scanner":
        eng_extract_sqlite.main()
    else:
        eng_editing.main()

if __name__ == "__main__":
    main()
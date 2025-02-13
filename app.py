import os
import base64
import streamlit as st
import logging

import config
import services
import yaml
import tempfile
import shutil
from pathlib import Path

def get_directory_structure(path):
    """Return a list of all subfolders in the given path"""
    path = Path(path)
    folders = []
    if path.exists():
        for item in path.rglob("*"):
            if item.is_dir():
                folders.append(str(item))
    return sorted(folders)

def clear_specific_folder(folder_path):
    """Clear all files in a specific folder"""
    try:
        folder = Path(folder_path)
        if folder.exists():
            for item in folder.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            return True
    except Exception as e:
        st.error(f"Error clearing folder {folder_path}: {str(e)}")
        return False

def clear_data_folder():
    try:
        data_dir = Path("data")
        if data_dir.exists():
            shutil.rmtree(data_dir)
            data_dir.mkdir(exist_ok=True)
            return True
    except Exception as e:
        st.error(f"Error clearing data folder: {str(e)}")
        return False

def generate_preview_pdf(yaml_content, resume_improver):
    try:
        temp_dir = Path(tempfile.gettempdir()) / "resume_preview"
        temp_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = temp_dir / "temp_resume.yaml"
        pdf_path = temp_dir / "preview_resume.pdf"

        yaml_dict = yaml.safe_load(yaml_content)
        yaml_dict["editing"] = False
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_dict, f)

        resume_improver.yaml_loc = str(yaml_path)
        resume_improver.pdf_loc = str(pdf_path)

        return resume_improver.create_pdf(auto_open=False)
    except Exception as e:
        st.error(f"Preview generation error: {str(e)}")
        return None

def generate_final_pdf(yaml_content, resume_improver, output_dir):
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = output_dir / "final_resume.yaml"
        pdf_path = output_dir / "final_resume.pdf"

        yaml_dict = yaml.safe_load(yaml_content)
        yaml_dict["editing"] = False
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_dict, f)

        resume_improver.yaml_loc = str(yaml_path)
        resume_improver.pdf_loc = str(pdf_path)

        return resume_improver.create_pdf(auto_open=False)
    except Exception as e:
        st.error(f"Final PDF generation error: {str(e)}")
        return None

def display_pdf(pdf_path):
    try:
        # Create a custom HTML component that uses PDF.js with a local file
        pdf_display = f"""
            <div style="width:100%; height:800px;">
                <object
                    data="pdf"
                    type="application/pdf"
                    width="100%"
                    height="100%"
                >
                    <p>It appears your browser doesn't support embedded PDFs.</p>
                </object>
            </div>
        """

        # Create a route for serving the PDF
        from streamlit.components.v1 import html
        import mimetypes
        mimetypes.add_type('application/pdf', '.pdf')

        # Read the PDF in chunks to handle large files
        def get_binary_file_downloader_html():
            with open(pdf_path, 'rb') as f:
                bytes = f.read()
                b64 = base64.b64encode(bytes).decode()
                # Use a data URL for smaller PDFs
                return f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800px" type="application/pdf"></iframe>'

        # Display the PDF
        st.markdown(get_binary_file_downloader_html(), unsafe_allow_html=True)

        # Add download button
        with open(pdf_path, "rb") as pdf_file:
            PDFbyte = pdf_file.read()

        st.download_button(
            label="📥 Download PDF",
            data=PDFbyte,
            file_name="resume.pdf",
            mime='application/pdf',
        )

    except Exception as e:
        st.error(f"PDF display error: {str(e)}")
        st.error("Please try downloading the PDF to view it.")

class StreamlitHandler(logging.Handler):
    def __init__(self, placeholder):
        super().__init__()
        self.placeholder = placeholder
        self.logs = []
        self.counter = 0

    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)
        log_text = "\n".join(self.logs)
        self.counter += 1
        self.placeholder.text_area("Logs", log_text, height=300, key=f"log_area_{self.counter}")

def main():
    st.title("Resume Tailoring Tool")

    if 'stage' not in st.session_state:
        st.session_state.stage = 'input'
        st.session_state.resume_improver = None
        st.session_state.yaml_content = None
        st.session_state.last_yaml = None

    # Add folder management in the sidebar
    with st.sidebar:
        st.subheader("Folder Management")

        # Create data directory if it doesn't exist
        data_dir = Path(config.DATA_PATH)
        data_dir.mkdir(exist_ok=True)

        # Get all subfolders
        folders = get_directory_structure(config.DATA_PATH)

        # Show main data folder with clear button
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write("📁 data")
        with col2:
            if st.button("❌", key="main_clear"):
                if clear_data_folder():
                    st.success("Data folder cleared!")
                    st.rerun()

        # Show subfolders with individual clear buttons
        for folder in folders:
            folder_path = Path(folder)
            relative_path = folder_path.relative_to(data_dir)
            indent = "    " * (len(folder_path.parts) - 1)

            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{indent}📁 {relative_path}")
            with col2:
                if st.button("❌", key=f"clear_{folder}"):
                    if clear_specific_folder(folder):
                        st.success(f"Cleared {relative_path}")
                        st.rerun()

    if st.session_state.stage == 'input':
        url = st.text_input("Enter Job URL:", placeholder="https://example.com/job/...")

        if st.button("Analyze Job"):
            if url:
                progress_bar = st.progress(0)
                log_placeholder = st.empty()
                logger = logging.getLogger()
                logger.setLevel(logging.INFO)
                handler = StreamlitHandler(log_placeholder)
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)

                try:
                    st.session_state.resume_improver = services.ResumeImprover(url)
                    progress_bar.progress(25)
                    st.session_state.resume_improver.create_draft_tailored_resume(
                        auto_open=False,
                        manual_review=False,
                        skip_pdf_create=True
                    )
                    with open(st.session_state.resume_improver.yaml_loc, 'r') as f:
                        st.session_state.yaml_content = f.read()
                    progress_bar.progress(100)
                    st.session_state.stage = 'review'
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                finally:
                    logger.removeHandler(handler)
            else:
                st.warning("Please enter a job URL")

    elif st.session_state.stage == 'review':
        edited_yaml = st.text_area("Review Resume YAML", st.session_state.yaml_content, height=400)

        if edited_yaml != st.session_state.last_yaml:
            st.session_state.last_yaml = edited_yaml
            pdf_path = generate_preview_pdf(edited_yaml, st.session_state.resume_improver)
            if pdf_path:
                st.session_state.pdf_path = pdf_path
                st.session_state.show_preview = True

        output_dir = st.text_input("Output Directory:", placeholder="/path/to/save/resume")

        if st.button("Save Final PDF"):
            if output_dir:
                pdf_path = generate_final_pdf(edited_yaml, st.session_state.resume_improver, output_dir)
                if pdf_path and os.path.exists(pdf_path):
                    st.success(f"PDF saved to: {pdf_path}")
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="Download PDF",
                        data=pdf_bytes,
                        file_name="resume.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("Please specify an output directory")

        if st.button("Start Over"):
            st.session_state.stage = 'input'
            st.rerun()

        if hasattr(st.session_state, 'show_preview') and hasattr(st.session_state, 'pdf_path'):
            st.subheader("PDF Preview")
            display_pdf(st.session_state.pdf_path)

if __name__ == "__main__":
    main()
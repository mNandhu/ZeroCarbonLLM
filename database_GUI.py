import streamlit as st
import os
from pathlib import Path
import timeit
import shutil
import fitz
import webbrowser

# Import necessary functions from create_database.py
from create_database import (
    llamaParse_pdf2md,
    pyMuPdf_pdf2md,
    load_md,
    split_text,
    save_to_chroma,
    getTextChunks,
    get_embedded_files
)

# Initialize session state for folder paths
if 'folder_paths' not in st.session_state:
    st.session_state.folder_paths = {
        "CHROMA_PATH": "chroma",
        "PDF_PATH": "data/pdfs",
        "MARKDOWN_PATH": 'data/markdowns/',
        "TEXT_PATH": "data/texts"
    }

st.set_page_config(page_title="ZeroCarbonLLM Database Creator", page_icon=":floppy_disk:")
st.title("ZeroCarbonLLM Database Creator")


# Function to get PDF page count
def get_page_count(file_path) -> int | str:
    if file_path.name.endswith(".md"):
        return -1
    else:
        with open(file_path, 'rb') as file:
            reader = fitz.open(file)
            return reader.page_count


# Function to display PDF files table
def display_files_table(files: list[Path] = None, file_path=st.session_state.folder_paths["PDF_PATH"]):
    if not files:
        files = list(Path(file_path).glob("*.pdf")) + list(Path(file_path).glob("*.txt"))
    else:
        updated_files = []
        for file in files:
            if file.name.endswith(".md"):
                pdf_file = Path(os.path.join(file_path, file.name.replace(".md", ".pdf")))
                if pdf_file.exists():
                    updated_files.append(pdf_file)
                else:
                    updated_files.append(file)
            else:
                updated_files.append(file)
        files = sorted(updated_files, key=lambda x: x.name)

    # Create a list of dictionaries for the table
    table_data = []
    for i, file in enumerate(files, start=1):
        page_count = get_page_count(file)
        table_data.append({
            "S.No": i,
            "Name": f"📄 {file.name}",
            "File type": "PDF" if file.name.endswith(".pdf") else
            ("Text" if file.name.endswith(".txt") else file.name.partition(".")[-1]),
            "Pages": page_count
        })

    # Display the table
    event = st.dataframe(table_data, hide_index=True, use_container_width=True, on_select="rerun",
                         selection_mode="single-row")
    if event['selection']['rows']:
        webbrowser.open(files[event['selection']['rows'][0]])


# --- Settings Sidebar ---
st.sidebar.header("Settings")

# Folder path settings
expander = st.sidebar.expander("Folder Paths")
for key, value in st.session_state.folder_paths.items():
    st.session_state.folder_paths[key] = expander.text_input(f"{key}:", value)

# PDF to Markdown conversion method
conversion_method = st.sidebar.radio(
    "PDF to Markdown Conversion Method",
    ("LlamaParse", "PyMuPDF")
)

# Reset options
reset_md = st.sidebar.checkbox("Reset Markdown Files", value=False, help="Check this box to delete existing Markdown "
                                                                         "files. Llamaparse/PyMuPDF"
                                                                         " will skip the files that "
                                                                         "are already in the markdown folder.")
reset_db = st.sidebar.checkbox("Reset Database", value=False, help="Check this box to delete the existing Chroma "
                                                                   "Database while creating a new one, if it exists."
                                                                   "Same as clicking "
                                                                   "\"Delete Current Database\" button.")

# Chunk size and overlap
chunk_size = st.sidebar.slider("Chunk Size", 500, 5000, 3500)
chunk_overlap = st.sidebar.slider("Chunk Overlap", 0, 1000, 1000)

# --- Sidebar end ---

# --- Main page UI ---
columns = st.columns([1, 1, 1, 1, 1])
with columns[0]:
    create_database_button = st.button("Create Database")
with columns[1]:
    reset_database_button = st.button("Delete Current Database")

# Display current database info as an expander
with st.expander("Current Database Info"):
    if os.path.exists(st.session_state.folder_paths["CHROMA_PATH"]):
        st.text(f"Chroma database found at: {os.path.abspath(st.session_state.folder_paths['CHROMA_PATH'])}")

        # Get embedded files and display count
        embedded_files = get_embedded_files()
        st.text(f"Total embedded files: {len(embedded_files)}")
        display_files_table(embedded_files)
    else:
        st.text("No existing Chroma database found.")

# Display PDF files table
st.header("PDF Files")
display_files_table()

# Add a section for uploading new PDF files
uploaded_files = st.file_uploader("Upload New PDF Files", accept_multiple_files=True, type="pdf")
# Add a button to upload the files
upload_files = st.button("Upload")

# --- Main page processes ---
if create_database_button:
    with st.spinner("Creating database..."):
        start_time = timeit.default_timer()

        # Step 1: Convert PDFs to Markdown
        st.text("Step 1: Converting PDFs to Markdown")
        if conversion_method == "LlamaParse":
            try:
                llamaParse_pdf2md(reset=reset_md, markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"],
                                  pdf_path=st.session_state.folder_paths["PDF_PATH"])
            except Exception as e:
                st.error(f"Error with LlamaParse: {str(e)}")
                st.info("Falling back to PyMuPDF...")
                pyMuPdf_pdf2md(reset=reset_md, markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"],
                               pdf_path=st.session_state.folder_paths["PDF_PATH"])
        else:
            pyMuPdf_pdf2md(reset=reset_md, markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"],
                           pdf_path=st.session_state.folder_paths["PDF_PATH"])

        # Step 2: Load and chunk Markdown files
        st.text("Step 2: Loading and chunking Markdown files")
        documents = load_md(markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"])
        chunks = split_text(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Step 3: Add text chunks
        st.text("Step 3: Adding text chunks")
        chunks.extend(getTextChunks(text_path=st.session_state.folder_paths["TEXT_PATH"]))

        # Step 4: Save to Chroma
        st.text("Step 4: Saving to Chroma database")
        save_to_chroma(chunks, reset=reset_db, chroma_path=st.session_state.folder_paths["CHROMA_PATH"])

        end_time = timeit.default_timer()
        st.success(f"Database created successfully in {end_time - start_time:.2f} seconds!")
if reset_database_button:
    with st.spinner("Resetting database..."):
        chroma_path = st.session_state.folder_paths["CHROMA_PATH"]
        if os.path.exists(chroma_path):  # Clear out the database, if reset
            try:
                start_time = timeit.default_timer()
                st.session_state.folder_paths["CHROMA_PATH"] = None
                shutil.rmtree(chroma_path)
                st.session_state.folder_paths["CHROMA_PATH"] = chroma_path

            except Exception as e:
                st.error(f"Error while deleting Chroma database: {str(e)}")
            else:
                end_time = timeit.default_timer()
                st.success(f"Database reset successfully in {end_time - start_time:.2f} seconds!")
        else:
            st.info("No existing Chroma database found.")
if uploaded_files and upload_files:
    for uploaded_file in uploaded_files:
        with open(os.path.join(st.session_state.folder_paths["PDF_PATH"], uploaded_file.name), "wb") as f:
            f.write(uploaded_file.getbuffer())
    st.success(f"Uploaded {len(uploaded_files)} file(s) successfully!")

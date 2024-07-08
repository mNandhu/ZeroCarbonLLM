import streamlit as st
import os
from pathlib import Path
import timeit
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

st.set_page_config(page_title="ZeroCarbonLLM - DBM", page_icon=":floppy_disk:")
st.title("ZeroCarbonLLM Database Manager")


# Function to get PDF page count
def get_page_count(file_path: Path) -> int:
    """
    Get the number of pages in a PDF/Text file
    If the file is not a PDF or Text file, returns -1
    :param file_path: Path to the file
    """
    if file_path.suffix not in ['.pdf', '.txt']:
        return -1
    else:
        with open(file_path, 'rb') as file:
            reader = fitz.open(file)
            return reader.page_count


# Function to display PDF files table
def display_files_table(files: list[Path] = None, file_path: str = st.session_state.folder_paths["PDF_PATH"]):
    """
    Display a table of files in the given folder as a streamlit dataframe
    Give either a list of files or the path to the folder
    Also, allows opening the file in the default application when selected
    :param files: List of files to display (Default: None)
    :param file_path: Path to the folder (Default: PDF_PATH)
    """
    if files is None:
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
        webbrowser.open(str(files[event['selection']['rows'][0]]))


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
                                                                         "files.Otherwise, Llamaparse/PyMuPDF"
                                                                         " will skip the files that "
                                                                         "are already in the markdown folder.")

# Chunk size and overlap
chunk_size = st.sidebar.slider("Chunk Size", 500, 5000, 3500)
chunk_overlap = st.sidebar.slider("Chunk Overlap", 0, 1000, 1000)

# --- Main page UI ---
columns = st.columns([1, 1, 1, 1, 1])
with columns[0]:
    create_database_button = st.button("Create new Database")
with columns[1]:
    reset_database_button = st.button("Delete Current Database")
with columns[2]:
    append_database_button = st.button("Append new files")

# --- Main page processes ---
if create_database_button:
    progress_text = "Creating Database. Please Wait.."

    my_bar = st.progress(0, text=progress_text)
    start_time = timeit.default_timer()

    # Step 1: Convert PDFs to Markdown
    with st.spinner("Converting PDFs to Markdown..."):
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
    my_bar.progress(0.25, text=progress_text)

    # Step 2: Load and chunk Markdown files
    with st.spinner("Loading and chunking Markdown files"):
        documents = load_md(markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"])
        chunks = split_text(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    my_bar.progress(0.50, text=progress_text)

    # Step 3: Add text chunks
    with st.spinner("Adding text chunks"):
        chunks.extend(getTextChunks(text_path=st.session_state.folder_paths["TEXT_PATH"]))
    my_bar.progress(0.75, text=progress_text)

    # Step 4: Save to Chroma
    with st.spinner("Saving to Chroma database"):
        save_to_chroma(chunks, chroma_path=st.session_state.folder_paths["CHROMA_PATH"])

    my_bar.progress(1.0, text="Database creation complete!")
    end_time = timeit.default_timer()
    st.toast(f"Database created successfully in {end_time - start_time:.2f} seconds!")
    st.rerun()

if reset_database_button:
    with st.spinner("Resetting database..."):
        start_time = timeit.default_timer()
        from langchain.vectorstores.chroma import Chroma

        db = Chroma(persist_directory=st.session_state.folder_paths["CHROMA_PATH"])
        db.delete_collection()
        end_time = timeit.default_timer()
        st.toast(f"Database reset successfully in {end_time - start_time:.2f} seconds!")
        st.rerun()

if append_database_button:
    progress_text = "Adding new files to Database. Please Wait.."

    my_bar = st.progress(0, text=progress_text)
    start_time = timeit.default_timer()

    # Step 1: Convert PDFs to Markdown
    with st.spinner("Converting PDFs to Markdown..."):
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
    my_bar.progress(0.25, text=progress_text)

    # Step 2: Load and chunk Markdown files
    with st.spinner("Loading and chunking Markdown files"):
        documents = load_md(markdown_path=st.session_state.folder_paths["MARKDOWN_PATH"],
                            include_only=[os.path.basename(file) for file in
                                          Path(st.session_state.folder_paths["MARKDOWN_PATH"]).glob("*.md")
                                          if file not in
                                          get_embedded_files("../chroma")])
        chunks = split_text(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    my_bar.progress(0.50, text=progress_text)
    # Step 3: Add text chunks
    with st.spinner(" Adding text chunks"):
        chunks.extend(getTextChunks(text_path=st.session_state.folder_paths["TEXT_PATH"],
                                    include_only=[os.path.basename(file) for file in
                                                  Path(st.session_state.folder_paths["TEXT_PATH"]).glob("*.txt")
                                                  if file not in
                                                  get_embedded_files("../chroma")]))
    my_bar.progress(0.75, text=progress_text)
    # Step 4: Save to Chroma
    with st.spinner("Saving to Chroma database"):
        save_to_chroma(chunks, chroma_path=st.session_state.folder_paths["CHROMA_PATH"], reset=False)
    my_bar.progress(1.0, text="Complete!")
    end_time = timeit.default_timer()
    st.toast(f"Files embedded successfully in {end_time - start_time:.2f} seconds!")
    st.rerun()

# --- Main page UI continued ---

# Display current database info as an expander
with st.expander("Current Database Info"):
    if os.path.exists(st.session_state.folder_paths["CHROMA_PATH"]):
        # Get embedded files and display count
        embedded_files = get_embedded_files(st.session_state.folder_paths["CHROMA_PATH"])
        if len(embedded_files) > 0:
            st.text(f"Chroma database found at: {os.path.abspath(st.session_state.folder_paths['CHROMA_PATH'])}")
            st.text(f"Total embedded files: {len(embedded_files)}")
            with st.spinner("Loading embedded files..."):
                display_files_table(embedded_files)
        else:
            st.text("No embedded files found in the Chroma database")

    else:
        st.text("No existing Chroma database found.")

# Display PDF files/ Text files as tabs
tab1, tab2 = st.tabs(["PDFs", "Texts"])
with tab1:
    st.header("PDF Files")
    with st.spinner("Loading files in PDF Path..."):
        display_files_table()
    uploaded_pdf_files = st.file_uploader("Upload New PDF Files", accept_multiple_files=True, type="pdf")
    upload_pdfs = st.button("Upload", key="pdf_upload")
    if upload_pdfs and uploaded_pdf_files:
        for uploaded_file in uploaded_pdf_files:
            with open(os.path.join(st.session_state.folder_paths["PDF_PATH"], uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded {len(uploaded_pdf_files)} file(s) successfully!")

with tab2:
    st.header("Text Files")
    with st.spinner("Loading files in Text Path..."):
        display_files_table(file_path=st.session_state.folder_paths["TEXT_PATH"])
    uploaded_text_files = st.file_uploader("Upload New Text Files", accept_multiple_files=True, type="txt")
    upload_texts = st.button("Upload Text Files", key="text_upload")
    if upload_texts and uploaded_text_files:
        for uploaded_file in uploaded_text_files:
            with open(os.path.join(st.session_state.folder_paths["TEXT_PATH"], uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded {len(uploaded_text_files)} file(s) successfully!")

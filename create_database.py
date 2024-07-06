"""
This script is used to create a database of embeddings from a set of documents.
It uses the following steps:
1. Convert PDFs to .md files using LlamaParse
2. Split the .md files into chunks
3. Embed the chunks using GoogleGenerativeAIEmbeddings
4. Save the embeddings to a Chroma database

Note:
Text Files are also split into chunks, if available
Text files are not processed by LlamaParse and are directly embedded.

The script can be run using the following command:
python create_database.py

The script uses the following environment variables:
1. GOOGLE_API_KEY: The API key for the Google Cloud Platform (If not found, SentenceTransformers is used)
2. LLAMA_CLOUD_API_KEY: The API key for the LlamaIndex API (For LlamaParse, If not found, PyMuPDF is used)

The script uses the following files:
1. data/pdfs: The directory containing the PDF files
2. data/markdowns: The directory containing the Markdown files
3. data/texts: The directory containing the text files (Optional)

The script creates the following files:
1. chroma: The directory containing the Chroma database
"""

import os  # File Handling
import shutil  # Deleting Existing Vector Embeddings
import timeit  # For Timing the Program
from pathlib import Path  # Path Handling

import pydantic.v1.error_wrappers  # Error Wrapper
from dotenv import load_dotenv  # Load Environment Variables
from langchain.schema import Document  # Document Schema
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Split Document into Chunks
from langchain.vectorstores.chroma import Chroma  # Vector Storage
from langchain_community.document_loaders import DirectoryLoader  # Load md files
from langchain_google_genai import GoogleGenerativeAIEmbeddings  # Embedding Function

load_dotenv()

CHROMA_PATH = "chroma"
PDF_PATH = "data/pdfs"
MARKDOWN_PATH = 'data/markdowns/'
TEXT_PATH = "data/texts"


def main():
    """
    Main Function to Create the Database
    """
    # Set reset to True if you want to delete the existing md files
    reset = False

    try:
        # Summarize Paper and convert to md
        llamaParse_pdf2md(reset=reset)
    except pydantic.v1.error_wrappers.ValidationError:
        # (Deprecated) Direct Conversion to .md
        print("LLAMA_CLOUD_API_KEY Not found, Using Direct Conversion to .md")
        pyMuPdf_pdf2md(reset=reset)
    finally:
        chunk_and_store()  # Chunk .md files, Embed and Save to Chroma


def getEmbeddingFunction():
    """
    Get the Embedding Function.
    If GOOGLE_API_KEY is found, use GoogleGenerativeAIEmbeddings
    Else, use SentenceTransformerEmbeddings
    :return: Embedding Function
    """
    try:
        embedding_function = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    except pydantic.v1.error_wrappers.ValidationError:
        print("GOOGLE_API_KEY Not found, using SentenceTransformers instead")
        # Embedding uses model "all-MiniLM-L6-v2" by default
        # Select Model from https://www.sbert.net/docs/pretrained_models.html
        # Runs Locally
        # set "device" : "cpu" , if you get a torch error
        from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

        embedding_function = SentenceTransformerEmbeddings(model_name="all-mpnet-base-v2", multi_process=True,
                                                           model_kwargs={"device": "cuda", },
                                                           encode_kwargs={"normalize_embeddings": True})
    return embedding_function


def getTextChunks(text_path=TEXT_PATH) -> list[Document]:
    """
    Load text files and split them into chunks
    :param text_path: Path to text files
    :return: List of Documents
    """
    print("\n Chunking text files")
    loader = DirectoryLoader(text_path, glob="*.txt")
    documents = loader.load()
    chunks = []
    if documents:
        chunks = split_text(documents, chunk_size=500, chunk_overlap=10)
    return chunks


def llamaParse_pdf2md(reset=False, pdf_path=PDF_PATH, markdown_path=MARKDOWN_PATH):
    """
    Use LlamaIndex's LlamaParse to summarize PDFs
    Input PDFs from PDF_PATH
    Output as .md in MARKDOWN_PATH
    Only converts missing .md files
    :param pdf_path: Path to PDFs   (Default: data/pdfs)
    :param markdown_path: Path to store .md files (Default: data/markdowns)
    :param reset: False by Default, If True then delete all files in MARKDOWN_PATH
    """

    from llama_parse import LlamaParse

    pdf_search = Path(pdf_path).glob("*.pdf")
    parsing_instruction = """The provided document is a research paper focusing on advancements and findings in the 
    field of Carbon Capture. It contains detailed analyses, experimental results, and discussions related to various 
    methods and technologies used for capturing carbon emissions. Exclude references, citations, and author 
    information. Include all factual data and any other metrics mentioned in the paper. Ensure that the summary presents 
    information in a structured manner for easy reference and analysis. Be Verbose and include all information in the 
    paper"""
    parser = LlamaParse(result_type="markdown", parsing_instruction=parsing_instruction)

    if reset:  # If folder exists, delete and create new
        shutil.rmtree(markdown_path)
    if not os.path.exists(markdown_path):
        os.mkdir(markdown_path)

    for file in pdf_search:
        if not os.path.exists(markdown_path + file.name.replace('.pdf', '.md')):
            # if input(f"Process the file {file.name} (Y/N)? ").lower() != "y": continue
            docs = parser.load_data(pdf_path + '/' + file.name)
            with open(markdown_path + file.name.replace('.pdf', '.md'), 'w', encoding="utf-8") as f:
                for doc in docs:
                    f.write(doc.text)
    else:
        print("All PDFs are converted to .md successfully!")


def pyMuPdf_pdf2md(reset=False, pdf_path=PDF_PATH, markdown_path=MARKDOWN_PATH):
    """
    Deprecated
    Use PyMuPDF to extract text directly from PDFs in PDF_PATH,
    Store as .md in MARKDOWN_PATH
    :param pdf_path: Path to PDFs   (Default: data/pdfs)
    :param markdown_path: Path to store .md files (Default: data/markdowns)
    :param reset: False by Default, If True then delete all files in MARKDOWN_PATH
    """

    import fitz  # To Open PDFs
    from modules.pymupdf_rag import to_markdown  # For Converting PDF to MD

    pdf_search = Path(pdf_path).glob("*.pdf")

    if reset and os.path.exists(markdown_path):
        shutil.rmtree(markdown_path)
        os.mkdir(markdown_path)

    for file in pdf_search:
        if reset or not os.path.exists(markdown_path + file.name.replace('.pdf', '.md')):
            print(f"Converting {file.name} to .md")
            with open(markdown_path + file.name.replace('.pdf', '.md'), 'w', encoding="utf-8") as f:
                doc = fitz.open(file)
                md_text = to_markdown(doc).strip()
                f.write(md_text)


def chunk_and_store():
    """
    Chunk the .md files and store them in a Chroma database
    """
    documents = load_md()
    chunks = split_text(documents)

    chunks.extend(getTextChunks())  # Add the text chunks

    start = timeit.default_timer()
    save_to_chroma(chunks)
    print("Time Taken:", timeit.default_timer() - start)


def load_md(markdown_path=MARKDOWN_PATH) -> list[Document]:
    """
    Load the .md files from the MARKDOWN_PATH
    :param markdown_path: Path to the .md files
    :return: List of documents
    """
    loader = DirectoryLoader(markdown_path, glob="*.md")
    documents = loader.load()
    return documents


def split_text(documents: list[Document], chunk_size: int = 3500, chunk_overlap: int = 1000) -> list[Document]:
    """
    Split the documents into chunks.
    :param documents: List of documents to split
    :param chunk_size: Size of each chunk
    :param chunk_overlap: Overlap between chunks
    :return: List of chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                                                   length_function=len, add_start_index=True, keep_separator=False,
                                                   strip_whitespace=True, )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")

    document = chunks[10]
    print(document.page_content)
    print(document.metadata)

    return chunks


def save_to_chroma(chunks: list[Document], reset=True, chroma_path=CHROMA_PATH):
    """
    Save the chunks to a Chroma database.
    :param chunks: List of documents to save
    :param reset: If True, delete the existing database
    :param chroma_path: Path to save the database
    """

    if reset and os.path.exists(chroma_path):  # Clear out the database, if reset
        shutil.rmtree(chroma_path)

    # Create a new DB from the documents.
    db = Chroma.from_documents(chunks, getEmbeddingFunction(), persist_directory=chroma_path)
    db.persist()
    print(f"Saved {len(chunks)} chunks to {chroma_path}.")


# Utility functions
def get_embedded_files(chroma_path=CHROMA_PATH) -> list[Path]:
    """
    Get the file paths of the documents that have been embedded
    :return: List of file paths, as absolute paths
    """
    db = Chroma(persist_directory=chroma_path, embedding_function=getEmbeddingFunction())
    return list(set(Path(i['source']) for i in db.get()['metadatas']))


if __name__ == "__main__":
    main()

# Back END
# PDF -> MD -> VectorEmbedding
import os
import shutil  # Deleting Existing Vector Embeddings
import timeit  # For Timing the Program

from langchain_community.document_loaders import DirectoryLoader  # Load md files
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Split Document into Chunks
from langchain.schema import Document

from langchain_google_genai import GoogleGenerativeAIEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings  # Embedding Function
# from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.vectorstores.chroma import Chroma  # Vector Storage

from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = "chroma"
PDF_PATH = "data/pdfs"
MARKDOWN_PATH = 'data/markdowns/'

# Embedding uses model "all-MiniLM-L6-v2" by default
# Select Model from https://www.sbert.net/docs/pretrained_models.html
# Runs Locally
# embedding_function = SentenceTransformerEmbeddings(model_name="all-mpnet-base-v2", multi_process=True,
#                                                    model_kwargs={"device": "cuda", },
#                                                    encode_kwargs={"normalize_embeddings": True})
embedding_function = GoogleGenerativeAIEmbeddings(model="models/embedding-001")


# .pdf TO .md
# .md TO Vector_Embedding
# Vector_Embedding to ChromaDb (Vector Data Base)

def main():
    pdf_to_md(reset=False)  # Set reset to True if md should be replaced
    generate_data_store()


def pdf_to_md(reset=False):
    import fitz  # To Open PDFs
    from pathlib import Path
    from modules.pymupdf_rag import to_markdown  # For Converting PDF to MD

    pdf_search = Path(PDF_PATH).glob("*.pdf")

    for file in pdf_search:
        if reset or not os.path.exists(MARKDOWN_PATH + file.name.replace('.pdf', '.md')):
            print(f"Converting {file.name} to .md")
            with open(MARKDOWN_PATH + file.name.replace('.pdf', '.md'), 'w', encoding="utf-8") as f:
                doc = fitz.open(file)
                md_text = to_markdown(doc).strip()
                f.write(md_text)


def generate_data_store():
    documents = load_documents()
    chunks = split_text(documents)

    start = timeit.default_timer()
    save_to_chroma(chunks)
    print("Time Taken:", timeit.default_timer() - start)


def load_documents():
    loader = DirectoryLoader(MARKDOWN_PATH, glob="*.md")
    documents = loader.load()
    return documents


def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3500,
        chunk_overlap=1000,
        length_function=len,
        add_start_index=True,
        keep_separator=False,
        strip_whitespace=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")

    document = chunks[10]
    print(document.page_content)
    print(document.metadata)

    return chunks


def save_to_chroma(chunks: list[Document]):
    # Clear out the database first.
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    # Create a new DB from the documents.
    db = Chroma.from_documents(
        chunks, embedding_function, persist_directory=CHROMA_PATH
    )

    db.persist()
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")


if __name__ == "__main__":
    main()

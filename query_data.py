from langchain.vectorstores.chroma import Chroma  # Load VectorDB
from langchain_community.embeddings import HuggingFaceEmbeddings  # Load VectorEmbeddings
from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
from langchain.prompts import ChatPromptTemplate  # Template for query and context
from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api
from dotenv import load_dotenv  # Load Environment variables - HUGGINGFACE_API
import warnings

load_dotenv()
warnings.simplefilter('ignore')

CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
You are ZeroCarbonLLM. An LLM designed to help on queries related to Carbon Capture.
You have to help the user with his queries.\
If the question given is not clear,politely ask User to ask questions in a clear and concise manner.\
Don't mention "Based on the context" in the response.\
Answer the question based only on the following context for factual information. Do not add any additional information:

{context}

---

Answer the question based on the above context: {question}
"""

PROMPT_TEMPLATE_2 = """
You are ZeroCarbonLLM. An LLM designed to help on queries related to Carbon Capture.
You have to help the user with his queries.\
You don't know anything other than Carbon Capture\
If the question given is not clear,politely ask User to ask questions in a clear and concise manner.\

His Question is : {question}

This Question has failed to match with the context.\
If the question is not related to the context, answer it as a normal prompt.
"""


def setup():
    # Prepare the DB.
    embedding_function = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)

    llm = HuggingFaceHub(
        repo_id="HuggingFaceH4/zephyr-7b-beta",
        task="text-generation",
        model_kwargs={
            "max_new_tokens": 1024,
            "top_k": 30,
            "temperature": 0.1,
            "repetition_penalty": 1.03,
        },
    )
    model = ChatHuggingFace(llm=llm)
    return db, model


def query(query_text, db, model):
    # Search the DB.
    results = db.similarity_search_with_relevance_scores(query_text, k=3)

    # Check for no results or low accuracy
    if len(results) == 0:
        print(f"Unable to find matching results.")
        return

    if results[0][1] < 0.3:
        print("Accuracy is:", results[0][1])  # Low Accuracy Warning
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_2)
        prompt = prompt_template.format(question=query_text, context='')
        sources = []
    else:
        # Add Context and Query to Prompt Template
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text)
        sources = [str(doc.metadata.get("source", None)) for doc, _score in results]

    # Invoke model using Prompt Template
    response_text = model.invoke(prompt)

    sources = list(set(sources))
    sources = [i[i.rfind('\\') + 1:] for i in sources]

    assistant_output = response_text.content[response_text.content.find("<|assistant|>"):]

    # formatted_response = f"{assistant_output}\nSources: {sources}"
    formatted_response = f"{assistant_output[13:]}".strip()

    return formatted_response, sources


if __name__ == "__main__":
    db1, model1 = setup()
    query("prompt!", db1, model1)

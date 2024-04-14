import os.path
import warnings
from langchain.vectorstores.chroma import Chroma  # Load VectorDB
from langchain_community.embeddings import HuggingFaceEmbeddings  # Load VectorEmbeddings
from langchain.prompts import ChatPromptTemplate  # Template for query and context
from dotenv import load_dotenv  # Load Environment variables - HUGGINGFACE_API

load_dotenv()
warnings.simplefilter('ignore')

ALL_MODELS = ("HuggingFace", "gemini-1.0-pro")
ACTIVE_MODELS = dict.fromkeys([i.lower() for i in ALL_MODELS])
LLM_MODEL = ALL_MODELS[0]

ACTIVE_DB = None
CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
You are ZeroCarbonLLM. A Large Language Model designed to help on queries related to Carbon Capture.
You have to help the user with his queries.\
If the question given is not clear,politely ask User to ask questions in a clear and concise manner.\
Following context comes from few research papers on Carbon Capture.\
The user doesn't know about the context so,\
DO NOT mention "Based on the context" or "according to context" or similar words in the response. \
DO NOT mention figure numbers, tables, or any other information that is not directly related to the question.\
Answer the question based only on the following context for factual information. Do not add any additional information:

{context}

---

Answer the question elaborately based on the above context: {question}
"""

PROMPT_TEMPLATE_2 = """
You are ZeroCarbonLLM. A Large Language Model designed to help on queries related to Carbon Capture.
You have to help the user with his queries.\
You don't know anything other than Carbon Capture\
If the question given is not clear,politely ask User to ask questions in a clear and concise manner.\

User's Question is : {question}

This Question has failed to bring up any relevant results in your DataBase.\
It is maybe a follow-up question related to the previous context.\
If the question is not related to the context, answer it as a normal prompt.\
You are trained on a small dataset, so you may not be able to answer all the user's questions.
"""

GREET_MESSAGE = """\
Hi, I am ZeroCarbonLLM. I am here to help you with your queries.\
You can ask me anything related to Carbon Capture.\
Currently, I am trained on a small dataset, so I may not be able to answer all your questions.\
Please ask your questions in a clear and concise manner.\
As of now, I can answer only one question at a time, and have a very short-term memory."""


def get_db() -> Chroma:
    """
    Load the Chroma DB
    :return: Chroma
    """
    embedding_function = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    return db


def setup(model: str, *, reset=False):
    """
    Set up the model or reload ACTIVE_MODELS
    :param model: Model Name
    :param reset: Reload the models
    :return:
    """
    model = model.lower()

    global LLM_MODEL
    LLM_MODEL = model.lower()

    if ACTIVE_MODELS[model] is None or reset:
        if model == "huggingface":
            ACTIVE_MODELS[model] = huggingface_setup()
        elif model == "gemini-1.0-pro":
            ACTIVE_MODELS[model] = gemini_v1_pro_setup()
        else:
            raise ValueError("Invalid Model")
    return ACTIVE_MODELS[model]


def huggingface_setup():
    from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
    from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api

    llm = HuggingFaceHub(repo_id="HuggingFaceH4/zephyr-7b-beta", task="text-generation",
                         model_kwargs={"max_new_tokens": 1024, "top_k": 30, "temperature": 0.1,
                                       "repetition_penalty": 1.03, }, )
    model = ChatHuggingFace(llm=llm)
    return model


def gemini_v1_pro_setup():
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GEN_API_KEY"))

    # Set up the model
    generation_config = {"temperature": 0.1, "top_k": 30, "max_output_tokens": 2048}

    safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, ]

    # noinspection PyTypeChecker
    model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                  safety_settings=safety_settings)

    convo = model.start_chat(history=[])

    return convo  # convo.send_message(prompt)  # print(convo.last.text)


def query(query_text: str, model, *, db: Chroma = None) -> tuple[str, list[str]]:
    """
    Query the model with the given text
    :param query_text: Prompt
    :param model: ChatModel
    :param db: Chroma DB to use
    :return: (Response,Sources)
    """
    if db is None:
        global ACTIVE_DB
        if ACTIVE_DB is None: ACTIVE_DB = get_db()
        db = ACTIVE_DB

    # Search the DB.
    results = db.similarity_search_with_relevance_scores(query_text, k=3)

    # Check for no results or low accuracy

    if len(results) == 0 or results[0][1] < 0.3:
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

    # Prompt model using Prompt Template
    print(prompt)

    if LLM_MODEL == "huggingface":
        # HuggingFace
        response_text = model.invoke(prompt)
        assistant_output = response_text.content[response_text.content.rfind("<|assistant|>"):]
        model_output = f"{assistant_output[13:]}".strip()
    elif LLM_MODEL == "gemini-1.0-pro":
        # Gemini
        model.send_message(prompt)
        model_output = model.last.text
    else:
        raise ValueError("Invalid Model")

    # Sources
    sources = [f"{os.path.basename(i)}".replace(".md", ".pdf") for i in set(sources)]

    return model_output, sources


if __name__ == "__main__":
    model1 = huggingface_setup()
    # model1 = gemini_v1_pro_setup()
    prompt_response, sources_used = query("prompt!", model1)

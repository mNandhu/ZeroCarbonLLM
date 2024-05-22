import os.path
import timeit
import warnings

import google.generativeai as genai
from dotenv import load_dotenv  # Load Environment variables - HUGGINGFACE_API
from keybert import KeyBERT
from langchain.prompts import ChatPromptTemplate  # Template for query and context
from langchain.vectorstores.chroma import Chroma  # Load VectorDB
from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api

load_dotenv()
warnings.simplefilter('ignore')

ALL_MODELS = ("HuggingFace", "gemini-1.0-pro", "ollama")
ACTIVE_MODELS = dict.fromkeys([i.lower() for i in ALL_MODELS])

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
If the question is unrelated to the context, treat it as a normal prompt
Answer the question based on the above context: {question}
"""

CONTEXT_TEMPLATE = """
You are an Accurate AI model designed to extract keywords from a question related to Carbon Capture.\
Your task is to identify the key terms in the question that can be used to search a \
database of research papers on Carbon Capture.\
If an unrelated query is asked, just return keyword "None",For Example,"Who are you?" returns "None"\
DO NOT ADD ANYTHING ELSE IN THE RESPONSE\
YOU RESPONSE SHOULD ONLY CONTAIN KEYWORDS or "None"
For example, if the question is 'What is Carbon Capture?', \
your response should be 'Carbon Capture, Definition, Meaning'. Separate the keywords by a comma.
Strict Rules:
Your response will be used to query the database directly without modification!
IF THE PROMPT IS UNRELATED TO CARBON CAPTURE, RETURN "NONE" !
Remember, your task is to provide keywords, Do not form a question or a sentence!
DO NOT ADD ANY ADDITIONAL INFORMATION OTHER THAN KEYWORDS!!!
ONLY RETURN KEYWORDS Related to CARBON CAPTURE and THE QUESTION!!!
DO NOT ADD ANY KEYWORDS THAR ARE NOT RELATED DIRECTLY TO THE QUESTION!!!
LIMIT THE NUMBER OF KEYWORDS TO LESS THAN 20 !!!
NOT MORE THAN 20 KEYWORDS !!!
USE A MINIMUM NUMBER OF KEYWORDS !!!
DO NOT REPEAT A KEYWORD!
DO NOT ADD ANY NOTES!!!

---
Your task is to extract the keywords from this question: "{question}"
---
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

PROMPT_TEMPLATE_FLW_UP = """
You are ZeroCarbonLLM. A Large Language Model designed to help on queries related to Carbon Capture.
You don't know anything other than Carbon Capture\
If the question given is not clear,politely ask User to ask questions in a clear and concise manner.\

User's Question is : {question}.

This is a follow-up question or a general prompt. Answer based on the previous context."""


def prompt_model(prompt: str, model_name: str):
    """
    Prompt the model with the given text.
    Prints the response in the console
    :param prompt: Prompt
    :param model_name: ChatModel
    :return: Response
    """
    model = load_model(model_name)
    match model_name:
        case "huggingface":
            # HuggingFace
            response_text = model.invoke(prompt)
            assistant_output = response_text.content[response_text.content.rfind("<|assistant|>"):]
            model_output = f"{assistant_output[13:]}".strip()
        case "gemini-1.0-pro":
            # Gemini
            model.send_message(prompt)
            model_output = model.last.text
        case "ollama":
            # Ollama-Llama3
            model_output = model.invoke(prompt)
        case _:
            print(f"Invalid {model_name=}")
            raise ValueError("Invalid Model")
    print("RESPONSE: ", model_output)
    return model_output


def get_default_db() -> Chroma:
    """
    Load default Chroma DB
    :return: Chroma
    """
    from create_database import getEmbeddingFunction
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=getEmbeddingFunction())
    return db


def load_model(model_name: str, *, reset=False) -> ChatHuggingFace | genai.ChatSession:
    """
    Set up the model or reload ACTIVE_MODELS
    :param model_name: Model Name
    :param reset: Reload the models
    :return:
    """
    model_name = model_name.lower()
    if ACTIVE_MODELS[model_name] is None or reset:
        if model_name == "huggingface":
            ACTIVE_MODELS[model_name] = huggingface_setup()
        elif model_name == "gemini-1.0-pro":
            ACTIVE_MODELS[model_name] = gemini_v1_pro_setup()
        elif model_name == "ollama":
            ACTIVE_MODELS[model_name] = ollama_setup()
        else:
            raise ValueError("Invalid Model")
    return ACTIVE_MODELS[model_name]


def huggingface_setup() -> ChatHuggingFace:
    """
    Set up the HuggingFace Model
    :return: ChatHuggingFace
    """
    llm = HuggingFaceHub(repo_id="HuggingFaceH4/zephyr-7b-beta", task="text-generation",
                         model_kwargs={"max_new_tokens": 2048, "top_k": 30, "temperature": 0.05,
                                       "repetition_penalty": 1.2, })
    model = ChatHuggingFace(llm=llm)
    return model


def gemini_v1_pro_setup() -> genai.ChatSession:
    """
    Set up the Gemini Model
    :return: ChatSession
    """

    # Set up the model
    genai.configure(api_key=os.getenv("GEN_API_KEY"))
    generation_config = {"temperature": 0.1, "top_k": 30, "max_output_tokens": 4096}

    safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}, ]

    # noinspection PyTypeChecker
    model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                  safety_settings=safety_settings)

    convo = model.start_chat(history=[])  # convo.send_message(prompt)  # print(convo.last.text)
    return convo


def ollama_setup():
    """
    Set up the Ollama Model
    :return: OllamaModel
    """
    import ollama
    import os

    class OllamaModel:
        """
        Custom handle to manage OllamaModel and history
        """

        def __init__(self, model_name):
            self.messages = []
            self.model_name = model_name
            os.system('start cmd /c ollama serve')

        def __str__(self):
            return self.model_name

        def invoke(self, prompt: str) -> str:
            self.messages.append({'role': 'user', 'content': prompt})
            try:
                response = ollama.chat(model=self.model_name, messages=self.messages, )
            except ollama.ResponseError:
                print("Model not found! Trying to pull it")
                ollama.pull(self.model_name)
                self.invoke(prompt)
            else:
                self.messages.append(response['message'])
                return response['message']['content']

        def clearChat(self):
            self.messages = []

    return OllamaModel("llama3")


def query(query_text: str, model_name: str, *, k: int = 10, db: Chroma = None, use_keybert=False,
          use_hugging_for_kw=True, ) -> tuple[str, list[str]]:
    """
    Query the model with the given text
    :param query_text: Prompt
    :param model_name: ChatModel
    :param k: Number of queries to retrieve from ChromaDB
    :param db: Chroma DB to load (If not provided, it will load the default DB from CHROMA_PATH)
    :param use_keybert: Use KeyBert to extract keywords
    :param use_hugging_for_kw: Use HuggingFaceLLM to extract keywords
    :return: (Response,Sources)
    """

    if db is None:
        global ACTIVE_DB
        if ACTIVE_DB is None:
            ACTIVE_DB = get_default_db()
        db = ACTIVE_DB

    # Get the keywords
    keywords = ''
    context_questions = ''

    if k > 0:
        if use_keybert:
            # Using KeyBert
            kw_model = KeyBERT()
            keywords = ','.join([i for i, j in kw_model.extract_keywords(query_text)])
            print("KeyBert Keywords", keywords)
        if use_hugging_for_kw:
            # Using HuggingFace
            context_template = ChatPromptTemplate.from_template(CONTEXT_TEMPLATE)
            context = context_template.format(question=query_text)
            context_questions = prompt_model(context, "huggingface")
            context_questions = context_questions.strip().lower()
            print(f"HuggingLLM Keywords: {context_questions}")
            if len(context_questions) >= 100:
                context_questions = context_questions[:100] + context_questions[
                                                              100:(100 + context_questions[100:].find(","))]

            if " none " in context_questions or '\"none\"' in context_questions or "'none'" in context_questions:
                context_questions = 'none'

        print('\n')

        keywords += f",{context_questions.strip()}".strip(' []()!.\t\n,`\'\"')
        print(f"Final Keywords: {keywords}")

        if context_questions == 'none':
            results = []  # No Keywords!
        else:
            results = db.similarity_search_with_relevance_scores(query_text, k=k)
    else:
        results = []

    # Check for Follow-up or no results or low accuracy
    if len(results) == 0 or results[0][1] < 0.4:
        if k < 1:
            prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_FLW_UP)  # Follow-up
        else:
            prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_2)  # No Results

        prompt = prompt_template.format(question=query_text, context='')
        sources = []
    else:
        # Add Context and Query to Prompt Template
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        print("Accuracy is:", results[0][1])
        print(f"\nCONTEXT:\n{context_text}\n\n")
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text)
        sources = [str(doc.metadata.get("source", None)) for doc, _score in results]

    # Prompt model using Prompt Template
    model_output = prompt_model(prompt, model_name)
    # Sources
    sources = [f"{os.path.basename(i)}".replace(".md", ".pdf") for i in set(sources)]

    return model_output, sources


if __name__ == "__main__":
    print("For Testing only, run \"streamlit run GUI.py\" to use the GUI.")

    query_model_name = "ollama"  # Ollama uses llama3 by default
    load_model(query_model_name)

    inp = input("\nEnter prompt: ")
    start = timeit.default_timer()
    print("Processing .... / \n")
    prompt_response, sources_used = query(inp, query_model_name)
    print(" \n\n Time Taken:", timeit.default_timer() - start)

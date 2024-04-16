import os.path
import warnings
from langchain.vectorstores.chroma import Chroma  # Load VectorDB
from langchain.prompts import ChatPromptTemplate  # Template for query and context
from dotenv import load_dotenv  # Load Environment variables - HUGGINGFACE_API
from keybert import KeyBERT, KeyLLM
from keybert.llm import TextGeneration

from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api
import google.generativeai as genai

import transformers
import timeit

load_dotenv()
warnings.simplefilter('ignore')

kw_model = KeyBERT()
kw_llm = None
ALL_MODELS = ("HuggingFace", "gemini-1.0-pro", "llama-2-7b")
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


def prompt_model(prompt: str, model_name: str):
    model = load_model(model_name)
    if model_name == "huggingface":
        # HuggingFace
        response_text = model.invoke(prompt)
        assistant_output = response_text.content[response_text.content.rfind("<|assistant|>"):]
        model_output = f"{assistant_output[13:]}".strip()
    elif model_name == "gemini-1.0-pro":
        # Gemini
        model.send_message(prompt)
        model_output = model.last.text
    elif model_name == "llama-2-7b":
        # Llama
        print("LLAMA PROMPT: ", prompt[:200] + "...")
        model_output = model.predict(prompt)
        model_output = model_output[0]['generated_text']
    else:
        print(f"Invalid {model_name=}")
        raise ValueError("Invalid Model")
    print("RESPONSE: ", model_output)
    return model_output


def get_db() -> Chroma:
    """
    Load the Chroma DB
    :return: Chroma
    """
    from create_database import embedding_function
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    return db


def load_model(model: str, *, reset=False) -> ChatHuggingFace | genai.ChatSession | transformers.Pipeline:
    """
    Set up the model or reload ACTIVE_MODELS
    :param model: Model Name
    :param reset: Reload the models
    :return:
    """
    model = model.lower()
    if ACTIVE_MODELS[model] is None or reset:
        if model == "huggingface":
            ACTIVE_MODELS[model] = huggingface_setup()
        elif model == "gemini-1.0-pro":
            ACTIVE_MODELS[model] = gemini_v1_pro_setup()
        elif model == "llama-2-7b":
            ACTIVE_MODELS[model] = llama_setup()
        else:
            raise ValueError("Invalid Model")
    return ACTIVE_MODELS[model]


def huggingface_setup():
    llm = HuggingFaceHub(repo_id="HuggingFaceH4/zephyr-7b-beta",
                         task="text-generation",
                         model_kwargs={"max_new_tokens": 2048, "top_k": 30, "temperature": 0.05,
                                       "repetition_penalty": 1.2, })
    model = ChatHuggingFace(llm=llm)
    return model


def gemini_v1_pro_setup():
    genai.configure(api_key=os.getenv("GEN_API_KEY"))

    # Set up the model
    generation_config = {"temperature": 0.1, "top_k": 30, "max_output_tokens": 4096}

    safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, ]

    # noinspection PyTypeChecker
    model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                  safety_settings=safety_settings)

    convo = model.start_chat(history=[])
    return convo  # convo.send_message(prompt)  # print(convo.last.text)


def llama_setup():
    from torch import bfloat16
    llama_start = timeit.default_timer()
    model_id = 'meta-llama/Llama-2-7b-chat-hf'
    # model_id = 'HuggingFaceH4/zephyr-7b-alpha'

    # 4-bit Quantization to load Llama 2 with less GPU memory
    bnb_config = transformers.BitsAndBytesConfig(
        load_in_4bit=True,
        load_in_8bit_fp32_cpu_offload=True,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=bfloat16
    )

    # Llama 2 Model & Tokenizer
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_id)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        quantization_config=bnb_config,
        device_map='cuda',
    )
    model.eval()

    # Our text generator
    generator = transformers.pipeline(
        model=model, tokenizer=tokenizer,
        task='text-generation',
        temperature=0.1,
        max_new_tokens=4096,
        repetition_penalty=1.1
    )

    print("Llama Model Loaded in:", timeit.default_timer() - llama_start)

    return generator


def query(query_text: str, model_name: str, *, k: int = 10, db: Chroma = None, use_keybert=False,
          use_hugging_for_kw=True,
          use_keyllm=False) -> tuple[str, list[str]]:
    """
    Query the model with the given text
    :param query_text: Prompt
    :param model_name: ChatModel
    :param k: Number of queries to retrieve from ChromaDB
    :param db: Chroma DB to load
    :param use_keybert: Use KeyBert to extract keywords
    :param use_hugging_for_kw: Use HuggingFaceLLM to extract keywords
    :param use_keyllm: Use keybert.keyllm(llama) to extract keywords
    :return: (Response,Sources)
    """

    if db is None:
        global ACTIVE_DB
        if ACTIVE_DB is None:
            ACTIVE_DB = get_db()
        db = ACTIVE_DB

    # Get the keywords
    keywords = ''
    context_questions = ''
    keyllm_words = ''

    if use_keybert:
        # Using KeyBert
        keywords = ','.join([i for i, j in kw_model.extract_keywords(query_text)])
        print("KeyBert Keywords", keywords)

    if use_hugging_for_kw:
        # Using HuggingFace - without keybert.keyllm
        context_template = ChatPromptTemplate.from_template(CONTEXT_TEMPLATE)
        context = context_template.format(question=query_text)
        context_questions = prompt_model(context, "huggingface")
        context_questions = context_questions.strip().lower()
        print(f"HuggingLLM Keywords: {context_questions}")
        if len(context_questions) >= 100:
            context_questions = context_questions[:100] + context_questions[
                                                          100:(100 + context_questions[100:].find(","))]

        if " none " in context_questions or '\"none\"' in context_questions or "'none'" in context_questions:
            context_questions = 'None'

    # Using LLama - with keybert.keyllm
    if use_keyllm:
        global kw_llm
        if kw_llm is None:
            prompt = """
            <s>[INST] <<SYS>>
    
            You are a helpful assistant specialized in extracting comma-separated keywords.
            You are to the point and only give the answer in isolation without any chat-based fluff.
    
            <</SYS>>
            I have the following document:
            - The website mentions that it only takes a couple of days to deliver but I still have not received mine.
    
            Please give me the keywords that are present in this document and separate them with commas.
            Make sure you to only return the keywords and say nothing else. For example, don't say: 
            "Here are the keywords present in the document"
            [/INST] meat, beef, eat, eating, emissions, steak, food, health, processed, chicken [INST]
    
            I have the following document:
            - [DOCUMENT]
    
            Please give me the keywords that are present in this document and separate them with commas.
            Make sure you to only return the keywords and say nothing else. For example, don't say: 
            "Here are the keywords present in the document"
            [/INST]
            """
            key_llm = TextGeneration(load_model("llama-2-7b"), prompt=prompt)
            kw_llm = KeyLLM(key_llm)
        keyllm_words = ','.join([','.join(i) for i in kw_llm.extract_keywords(query_text)]) + ','
        print("KeyLLM Keywords :", keyllm_words)

    print('\n')

    keywords += f",{keyllm_words}{context_questions.strip()}".strip(' []()!.\t\n,`\'\"')
    print(f"Final Keywords: {keywords}")

    if keywords and context_questions != "None":
        results = db.similarity_search_with_relevance_scores(keywords, k=k)
    else:
        results = db.similarity_search_with_relevance_scores(query_text, k=k)

    # Check for no results or low accuracy
    if len(results) == 0 or results[0][1] < 0.4:
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_2)
        prompt = prompt_template.format(question=query_text, context='')
        sources = []
    else:
        print("Accuracy is:", results[0][1])
        # Add Context and Query to Prompt Template
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
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
    # while True:
    #     print(prompt_model(model_name="llama-2-7b", prompt=input("Enter Query: ")))

    load_model("huggingface")
    # while True:

    inp = input("\nEnter prompt: ")
    start = timeit.default_timer()
    print("Processing .... / \n")
    prompt_response, sources_used = query(inp, "huggingface")
    # print(prompt_response) Already printed in prompt...

    print(" \n\n Time Taken:", timeit.default_timer() - start)

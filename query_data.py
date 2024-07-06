import os.path  # For file paths
import timeit  # For measuring time
import warnings  # For ignoring warnings
from dotenv import load_dotenv  # Load Environment variables - HUGGINGFACE_API
from keybert import KeyBERT  # For Keyword Extraction
from langchain.prompts import ChatPromptTemplate  # Template for query and context
from langchain.vectorstores.chroma import Chroma  # Load VectorDB
from langchain.schema import Document  # Document Schema (for type reference)

# Custom Modules
import modules.prompt_templates as templates  # Prompt Templates
from modules.ModelHandle import ModelHandler

load_dotenv()
warnings.simplefilter('ignore')

CHROMA_PATH = "chroma"


class QueryHandler:
    def __init__(self, db: Chroma = None):
        """
        Initialize the Query Handler
        :param db: Chroma DB to load (If not provided, it will load the default DB from CHROMA_PATH)
        """
        self.model_handler = ModelHandler()
        self.db = db if db else self.get_default_db()

        # Model Name : Model Type ; Initialized with default params
        self.ALL_MODELS = {"HuggingFace/Zephyr": "huggingface", "Gemini V1 Pro": "gemini-1.0-pro",
                           "Llama3-Local": "ollama",
                           "Llama3-API": "groq"}

        self.kw_llm = "groq"  # Type of LLM for keyword extraction
        self.relv_llm = "gemini-1.0-pro"

    @staticmethod
    def get_default_db() -> Chroma:
        """
        Load default Chroma DB
        :return: Chroma
        """
        from create_database import getEmbeddingFunction
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=getEmbeddingFunction())
        return db

    def keyword_extraction(self, query_text: str, use_keybert: bool = False, use_llm_for_kw: bool = True) \
            -> tuple[str, bool]:
        """
        Extract keywords from the given text
        :param query_text: Prompt
        :param use_keybert: Use KeyBert to extract keywords
        :param use_llm_for_kw: Use HuggingFaceLLM to extract keywords.
        :return: Keywords, No Keywords
        """
        keywords = ''
        context_questions = ''
        if use_keybert:
            # Using KeyBert
            kw_model = KeyBERT()
            keywords = ','.join([i for i, j in kw_model.extract_keywords(query_text)])
            print("KeyBert Keywords", keywords)
        if use_llm_for_kw:
            self.model_handler.load_model("keyLLM", self.kw_llm)  # Create model with separate history
            # Using LLM for Keywords (may give gibberish sometimes, Depends on the model)

            context = ChatPromptTemplate.from_template(templates.CONTEXT_TEMPLATE).format(question=query_text)
            context_questions = self.model_handler.prompt_model(context, "keyLLM", echo=False)
            context_questions = context_questions.strip().lower()
            print(f"KeyLLM Keywords: {context_questions}")

            # Extract the first 100 characters + rest of the last word, and remove garbage
            if len(context_questions) >= 100:
                context_questions = context_questions[:100] + context_questions[
                                                              100:(100 + context_questions[100:].find(","))]
            # If LLM thinks there are no keywords, it should output "none"
            # Test for "none" in the string
            if " none " in context_questions or '\"none\"' in context_questions or "'none'" in context_questions:
                context_questions = 'none'
            keywords += f",{context_questions.strip()}"
        keywords = keywords.strip(' []()!.\t\n,`\'\"')

        return keywords, context_questions == 'none'

    def mix_similarity_and_keyword(self, query_text: str, keywords: str, keyword_weight: float = 0.5, k: int = 10):
        """
        Mix the similarity search with keyword search
        :param query_text: Prompt
        :param keywords: Keywords
        :param keyword_weight: Weight of the keywords
        :param k: Number of queries to retrieve from ChromaDB
        :return: List of tuples
        """
        assert 0 <= keyword_weight <= 1, "Keyword weight should be between 0 and 1"
        no_of_sim_results = int(k * keyword_weight)
        keyword_results = []
        results = []

        # Get the keyword search results
        if no_of_sim_results < k:
            keyword_results = self.db.similarity_search_with_relevance_scores(keywords, k=k - no_of_sim_results)
        if no_of_sim_results > 0:
            # Get the similarity search results
            results = self.db.similarity_search_with_relevance_scores(query_text, k=no_of_sim_results)

        # Mix the results
        mixed_results = keyword_results + results
        mixed_results.sort(key=lambda x: x[1], reverse=True)  # Sort based on relevance score
        return mixed_results

    def llm_relevance_filter(self, prompt: str, results: list[tuple[Document, float]] | list[None]):
        """
        Filter the results based on relevance
        :param prompt: Question used to prompt
        :param results: List of tuples
        :return: None
        """
        import json
        prompt_template = ChatPromptTemplate.from_template(templates.relevance_text)

        filtered_docs = []
        response = dict()
        for doc, score in results:
            prompt_with_content = prompt_template.format(context=doc.page_content, question=prompt)
            try:
                self.model_handler.load_model("relevanceLLM", self.relv_llm)
                response = self.model_handler.prompt_model(prompt_with_content, "relevanceLLM", echo=False)
                print(repr(response))
                response = json.loads(response[response.find("{"):response.find("}") + 1])
            except json.JSONDecodeError:
                print("Error decoding json, using ollama/llama3 instead")
                self.model_handler.load_model("jsonModel", "ollama", reset=False, query_model="llama3",
                                              output_format="json")
                response = self.model_handler.prompt_model(prompt_with_content, "jsonModel", echo=False)
            finally:
                if response.get("score") in ["yes", True]:
                    if doc.page_content not in [i.page_content for i, j in filtered_docs]:
                        filtered_docs.append((doc, score))

        print(f"Removed {len(results) - len(filtered_docs)} irrelevant documents from {len(results)}")
        return filtered_docs

    def query(self, query_text: str, model_name: str, k: int = 10, use_keybert: bool = False,
              use_llm_for_kw: bool = True, filter_irrelevant: bool = True, keyword_and_similarity_mix: float = 0.5) \
            -> tuple[str, list[str]]:
        """
        Query the model with the given text
        :param query_text: Prompt
        :param model_name: ChatModel
        :param k: Number of queries to retrieve from ChromaDB
        :param use_keybert: Use KeyBert to extract keywords
        :param use_llm_for_kw: Use HuggingFaceLLM to extract keywords
        :param filter_irrelevant: Filter the queries based on relevance
        :param keyword_and_similarity_mix: Mix the results from similarity and keyword search
        :return: (Response,Sources)
        """

        # Get the keywords
        if k > 0:
            extracted_kw, no_keyword = self.keyword_extraction(query_text, use_keybert, use_llm_for_kw)
            print(f"Final Keywords: {extracted_kw}")
            if no_keyword:
                results = []  # No Keywords!
            elif extracted_kw:
                results = self.mix_similarity_and_keyword(query_text, extracted_kw,
                                                          keyword_weight=keyword_and_similarity_mix,
                                                          k=k)
            else:
                results = self.db.similarity_search_with_relevance_scores(query_text, k=k)

        else:
            results = []

        # Check for Follow-up or no results or low accuracy
        if len(results) == 0 or results[0][1] < 0.7:
            if k < 1:
                prompt_template = ChatPromptTemplate.from_template(templates.PROMPT_TEMPLATE_FLW_UP)  # Follow-up
            else:
                prompt_template = ChatPromptTemplate.from_template(templates.PROMPT_TEMPLATE_2)  # No Results

            prompt = prompt_template.format(question=query_text, context='')
            sources = []
        else:
            # Add Context and Query to Prompt Template
            if filter_irrelevant:
                results = self.llm_relevance_filter(query_text, results)  # Filter the queries based on relevance
            context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
            print("Accuracy is:", results[0][1])
            print(f"\nCONTEXT:\n{context_text}\n".replace('\n\n', '\n'))

            prompt = ChatPromptTemplate.from_template(templates.PROMPT_TEMPLATE).format(context=context_text,
                                                                                        question=query_text)
            sources = [str(doc.metadata.get("source", None)) for doc, _score in results]

        # Prompt model using Prompt Template, Sources
        model_output = self.model_handler.prompt_model(prompt, model_name)
        sources = [f"{os.path.basename(i)}".replace(".md", ".pdf") for i in set(sources)]

        return model_output, sources


if __name__ == "__main__":
    print("For Testing only, run \"streamlit run GUI.py\" to use the GUI.")
    query_handle = QueryHandler()

    query_model_name = "any_name"  # Ollama uses llama3 by default
    query_handle.model_handler.load_model(query_model_name, "groq")

    inp = input("\nEnter prompt: ")
    start = timeit.default_timer()
    print("Processing .... / \n")
    prompt_response, sources_used = query_handle.query(inp, query_model_name,
                                                       use_llm_for_kw=False,
                                                       filter_irrelevant=True,
                                                       k=12)
    print(" \n\n Time Taken:", timeit.default_timer() - start)

import os.path  # For file paths
from dotenv import load_dotenv, find_dotenv  # Load Environment variables - HUGGINGFACE_API
from typing import Callable, Any  # For Type Hinting


class ModelHandler:
    """
    Model Handler to manage the models and their history.
    Usage:
    1. Load the Model using load_model()
    2. Prompt the Model using prompt_model()

    Example:
        model_handle = ModelHandler()
        model_handle.load_model(model_name="AnyName",model_type="groq")
        output = model_handle.prompt_model(model_name="groq",prompt="Hey!",echo=False)

    Note: Each model has a unique name (case-insensitive), which can be used to prompt the model.
     This is done to use multiple models of the same type.

    Model types available by default:
        1. HuggingFace  (zephyr-7b-beta)
        2. Gemini-1.0-Pro
        3. Ollama    (llama3)
        4. Groq     (llama3-70b-8192)

    To add a new model:
    1. Add the model setup in __get_model_setup() (as a function which will return any model object)
    2. Add the model type in __get_model_setup()  (as a key-value pair)
    3. Add the case for getting the response in prompt_model() (Logic to get the response from the model object)

    Note: Any arguments required for the model setup can be passed as kwargs in load_model()
    """

    def __init__(self):
        # Add a model and its setup in get_model_setup()
        self.ACTIVE_MODELS = dict()
        load_dotenv(find_dotenv())  # Load Environment Variables

    def prompt_model(self, prompt: str, model_name: str, echo: bool = True) -> str | None:
        """
        Prompt the model with the given text.
        Prints the response in the console
        :param prompt: Prompt
        :param model_name: ChatModel
        :param echo: If True, Print the response implicitly.
        :return: Response
        """
        model_info = self.ACTIVE_MODELS.get(model_name.lower())  # Get the model's type and name
        model_output = None

        if model_info is None:
            raise ValueError("Model not found. Load a Model, before prompting using load_model()")
        else:
            model_type, model = model_info
            match model_type:
                case model_type if model_type in ["huggingface", "groq"]:
                    # Langchain (HuggingFace, Groq)
                    model.run(prompt)
                    response = model.memory.chat_memory.messages[-1].content
                    if "<|assistant|>" in response:
                        assistant_output = response[response.rfind("<|assistant|>"):]
                        model_output = f"{assistant_output[13:]}".strip()
                    else:
                        model_output = response
                case "gemini-1.0-pro":
                    # Gemini
                    model.send_message(prompt)
                    model_output = model.last.text
                case "ollama":
                    # Ollama-Llama3
                    model_output = model.invoke(prompt)
                # Add new models here (case model_type) : model_output = model.invoke(prompt)
                case _:
                    print(f"Invalid {model_type=}")
        if echo:
            print("RESPONSE: ", model_output)
        return model_output

    def load_model(self, model_name: str, model_type: str, reset=False, **kwargs) -> tuple[str, Any]:
        """
        Load the Model.
        :param model_name: Model Name
        :param model_type: Model Type
        :param reset: Reset the Model, Default: False
        :param kwargs: Model Arguments
        :return: Model type, Model
        """
        model_name = model_name.lower()
        if self.ACTIVE_MODELS.get(model_name) is None or reset:
            print("Loading Model")
            model_setup = self.__get_model_setup(model_type)
            if model_setup:
                self.ACTIVE_MODELS[model_name] = (model_type, model_setup(**kwargs))
            else:
                raise ValueError("Invalid Model type")
        return self.ACTIVE_MODELS[model_name]

    def __get_model_setup(self, model_type: str) -> Callable:
        """
        Get the Model Setup Function
        :param model_type: Model Type
        :return: Model Setup Function Handle
        """

        # Add new model setups here, return any model object ... It can be accessed in prompt_model() as model
        def huggingface_setup(repo_id="HuggingFaceH4/zephyr-7b-beta", temperature=0.5):
            from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
            from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api
            from langchain import ConversationChain  # Conversation Chain
            from langchain.memory import ConversationBufferMemory  # Memory for Conversation
            """
            Set up the HuggingFace Model
            :return: ConversationChain
            """
            llm = HuggingFaceHub(repo_id=repo_id, task="text-generation",
                                 model_kwargs={"max_new_tokens": 2048, "top_k": 30, "temperature": temperature,
                                               "repetition_penalty": 1.2, })
            model = ChatHuggingFace(llm=llm)
            model_chain = ConversationChain(
                llm=model,
                memory=ConversationBufferMemory()
            )
            return model_chain

        def gemini_v1_pro_setup(temperature=0.1):
            # For Gemini Model
            import google.generativeai as genai
            """
            Set up the Gemini Model
            :return: ChatSession
            """

            # Set up the model
            genai.configure(api_key=os.getenv("GEN_API_KEY"))
            generation_config = {"temperature": temperature, "top_k": 30, "max_output_tokens": 4096}

            safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                               {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                               {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                               {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}, ]

            # noinspection PyTypeChecker
            model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                          safety_settings=safety_settings)

            convo = model.start_chat(history=[])  # convo.send_message(prompt)  # print(convo.last.text)
            return convo

        def ollama_setup(query_model="llama3", output_format="", temperature=-1):
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

                def __init__(self, model_name, out_format, temp=0.5):
                    self.messages = []
                    self.model_name = model_name
                    self.format = out_format
                    self.temperature = temp  # Not yet implemented
                    print("Starting Ollama Server")
                    os.system('start cmd /c ollama serve')

                def __str__(self):
                    return self.model_name

                def invoke(self, prompt: str) -> str | dict:
                    self.messages.append({'role': 'user', 'content': prompt})
                    try:
                        response = ollama.chat(model=self.model_name, messages=self.messages, format=self.format)
                    except ollama.ResponseError as e:
                        print(e)
                        print(f"If Model not found! Trying Pulling it using: ollama pull {self.model_name}")
                    else:
                        self.messages.append(response['message'])

                        if self.format == 'json':
                            from json import loads
                            response = response['message']['content']
                            return loads(response[response.find("{"):response.find("}") + 1])
                        else:
                            return response['message']['content']

                def clearChat(self):
                    self.messages = []

            return OllamaModel(query_model, out_format=output_format, temp=temperature)

        def groq_setup(query_model="llama3-70b-8192", temperature=0, output_format="text"):
            from langchain_groq import ChatGroq
            from langchain import ConversationChain
            from langchain.memory import ConversationBufferMemory
            if output_format == "json": output_format = "json_object"
            model = ChatGroq(temperature=temperature, model_name=query_model, response_format={"type": output_format})
            model_chain = ConversationChain(
                llm=model,
                memory=ConversationBufferMemory()
            )
            return model_chain

        models = {"huggingface": huggingface_setup, "gemini-1.0-pro": gemini_v1_pro_setup, "ollama": ollama_setup,
                  "groq": groq_setup}

        return models.get(model_type)


if __name__ == '__main__':
    model_handle = ModelHandler()
    model_handle.load_model('llama3', 'ollama')

    query_prompt = input("Prompt: ")
    while query_prompt:
        model_handle.prompt_model(query_prompt, 'llama3')
        query_prompt = input("Prompt: ")

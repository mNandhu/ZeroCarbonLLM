import os.path  # For file paths
from dotenv import load_dotenv, find_dotenv  # Load Environment variables - HUGGINGFACE_API
from typing import Callable, Any  # For Type Hinting


class ModelHandler:
    def __init__(self):
        # Add a model and its setup in get_model_setup()
        self.ACTIVE_MODELS = dict()
        load_dotenv(find_dotenv())  # Load Environment Variables

    def prompt_model(self, prompt: str, model_name: str, echo: bool = True) -> str | None:
        """
        Prompt the model with the given text.
        Prints the response in the console
        :param prompt: Prompt
        :param echo: Print the response
        :param model_name: ChatModel
        :return: Response
        """
        model_info = self.ACTIVE_MODELS.get(model_name.lower())  # Get the model's type and name
        model_output = None

        if model_info is None:
            raise ValueError("Model not found. Load a Model, before prompting using load_model()")
        else:
            model_type, model = model_info
            match model_type:
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

        def huggingface_setup():
            from langchain_community.chat_models.huggingface import ChatHuggingFace  # LLM for RAG
            from langchain_community.llms import HuggingFaceHub  # Access HuggingFace LLM using api
            """
            Set up the HuggingFace Model
            :return: ChatHuggingFace
            """
            llm = HuggingFaceHub(repo_id="HuggingFaceH4/zephyr-7b-beta", task="text-generation",
                                 model_kwargs={"max_new_tokens": 2048, "top_k": 30, "temperature": 0.05,
                                               "repetition_penalty": 1.2, })
            model = ChatHuggingFace(llm=llm)
            return model

        def gemini_v1_pro_setup():
            # For Gemini Model
            import google.generativeai as genai
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

        def ollama_setup(query_model="llama3", output_format=""):
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

                def __init__(self, model_name, out_format):
                    self.messages = []
                    self.model_name = model_name
                    self.format = out_format
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

            return OllamaModel(query_model, out_format=output_format)

        models = {"huggingface": huggingface_setup, "gemini-1.0-pro": gemini_v1_pro_setup, "ollama": ollama_setup}

        return models.get(model_type)

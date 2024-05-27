# ZeroCarbonLLM Project

This Project is an implementation of a RAG Chatbot that is using a Database of Research Papers to answer questions
about Carbon Capture.
This is a Team Project made possible by our Professor, Dr.Kritesh Kumar Gupta.
It was an awesome experience working on this project, and me and my team look forward to do 
more fun projects in the future!

![image](/images/prompt_example.png)
---
## Installation
1. Install the required packages:\
```pip install -r requirements.txt```

2. Create a .env file in the root directory and add your API Keys:\
```HUGGINGFACEHUB_API_TOKEN="YOUR_HUGGING_FACE_API_TOKEN"```
If you still face issues, try ```huggingface-cli login```in the terminal\
```GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY"```\
```LLAMA_CLOUD_API_KEY = "YOUR_LLAMA_CLOUD_API_KEY"```\
```GROQ_API_KEY = "YOUR_GROQ_API"```
3. For the first run, to create a Vector Database, run \
```py create_database.py```\
Add your files in "data\pdfs"
Add texts in "data\texts" (Optional)(Text files are not preprocessed)

4. Run the GUI using the following command\
```streamlit run GUI.py```
---
## Working
![image](/images/flowdiagram.png)

Gemini QA-Pair generation is not a part of this code, please visit [Google AI Studio](https://aistudio.google.com)
and generate QP pairs with a PDF and add response to the text folder!
---
## Related Links
1. [HuggingFace](https://huggingface.co/settings/tokens)
2. [LlamaCloud](https://cloud.llamaindex.ai/)
3. [Google AI Studio](https://aistudio.google.com)
4. [Groq Cloud](https://console.groq.com/keys)

## Note

You may face dependency issues with multiple modules used in this program
So, it is recommended to use Python 3.10.6 for this project



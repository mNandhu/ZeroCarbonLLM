# ZeroCarbonLLM Project

This Project is an implementation of a RAG Chatbot that is using a Database of Research Papers to answer questions
about Carbon Capture

![image](/images/prompt_example.png)
## Installation
1. Install the required packages:\
```pip install -r requirements.txt```

2. Create a .env file in the root directory and add your HuggingFace API Key:\
```HUGGINGFACEHUB_API_TOKEN="YOUR_HUGGING_FACE_API_TOKEN"```\
If you still face issues, try logging in by entering ```huggingface-cli login```in the terminal

3. For the first run, to create a Vector Database, run \
```py create_database.py```\
Add your files in "data\pdfs"

4. Run the GUI using the following command\
```streamlit run GUI.py```

## Note

You may face dependency issues with multiple modules used in this program
So, it is recommended to use Python 3.10.6 for this project



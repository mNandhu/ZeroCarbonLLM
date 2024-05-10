import streamlit as st
from streamlit_chat import message
import query_data

# Setting page title and header
st.set_page_config(page_title="ZeroCarbonLLM", page_icon=":robot_face:")
st.markdown("<h2 style='text-align: center;'>ZeroCarbonLLM</h2>", unsafe_allow_html=True)

# Initialise session state variables
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}, ]

message(query_data.GREET_MESSAGE, key='0_startup')

st.sidebar.title("Settings")
model_name = st.sidebar.radio("Choose a model:", query_data.ALL_MODELS).lower()
k_queries = st.sidebar.slider("Queries to retrieve from db", 0, 20, 8,
                              help="Number of Queries affects the accuracy of the model, depends on the documents "
                                   "embedded")
st.sidebar.write("KeyWord Extraction")
use_hugging_for_kw = st.sidebar.checkbox("Use HuggingFaceLLM", value=True, help="Checking this box uses a remote "
                                                                                "\"HuggingFace/zephyr-7b-beta\" model "
                                                                                "to extract the "
                                                                                "keywords from the prompt to "
                                                                                "efficiently lookup in the database",
                                         disabled=k_queries < 1)

use_keybert = st.sidebar.checkbox("Use KeyBert", help="Checking this box uses the Keybert module to extract the "
                                                      "keywords. This does not use an LLM", disabled=k_queries < 1)

use_keyllm = st.sidebar.checkbox("Use KeyLLM", help="Checking this box uses a local llama-2-7b model to extract the "
                                                    "keywords from the prompt ", disabled=k_queries < 1)
clear_button = st.sidebar.button("Clear Conversation", key="clear")

# Load the model
query_data.load_model(model_name)

# reset everything
if clear_button:
    st.session_state['generated'] = []
    st.session_state['past'] = []
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    st.session_state['model_name'] = []


# generate a response
def generate_response(prompt, query_model_name, k, keybert, keyhugging, keyllm):
    st.session_state['messages'].append({"role": "user", "content": prompt})

    response, sources = query_data.query(query_text=prompt, model_name=query_model_name, k=k, use_keybert=keybert,
                                         use_hugging_for_kw=keyhugging, use_keyllm=keyllm)

    if sources:
        response += "\n\nSources🔬 : " + ', '.join(
            [f"{index}.{source}" for index, source in enumerate(sources, start=1)])
    else:
        response += "\n\n⚠️No Sources used"
    st.session_state['messages'].append({"role": "assistant", "content": f'{response}'})

    # print(st.session_state['messages'])

    return response


# container for chat history
response_container = st.container()
# container for text box
container = st.container()

with container:
    with st.form(key='my_form', clear_on_submit=True):
        user_input = st.text_area("You:", key='input', height=100)
        submit_button = st.form_submit_button(label='Send')

    if submit_button and user_input:
        output = generate_response(user_input, model_name, k_queries, keybert=use_keybert,
                                   keyhugging=use_hugging_for_kw, keyllm=use_keyllm)
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(output)

if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
            message(st.session_state["generated"][i], key=str(i))

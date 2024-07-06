import streamlit as st
from streamlit_chat import message
import query_data
import modules.prompt_templates as t

# Setting page title and header
st.set_page_config(page_title="ZeroCarbonLLM", page_icon=":robot_face:")
st.markdown("<h2 style='text-align: center;'>ZeroCarbonLLM</h2>", unsafe_allow_html=True)


# Create a QueryHandler object, to persist the object across runs
@st.cache_resource
def get_query_handler():
    print("Backend Call")
    return query_data.QueryHandler()


query_handler = get_query_handler()
# Initialise session state variables
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}, ]

message(t.GREET_MESSAGE, key='0_startup', avatar_style='lorelei-neutral', seed='Molly')

st.sidebar.title("Settings")
model_name = st.sidebar.radio("Choose a model:", query_handler.ALL_MODELS.keys())
k_queries = st.sidebar.slider("Queries to retrieve from db", 0, 30, 8,
                              help="Number of Queries affects the accuracy of the model, depends on the documents "
                                   "embedded")

st.sidebar.write("KeyWord Extraction")

use_keybert = st.sidebar.checkbox("Use KeyBert", help="Checking this box uses the Keybert module to extract the "
                                                      "keywords. This does not use an LLM. Doesn't add new words",
                                  disabled=k_queries < 1)
use_llm_for_kw = st.sidebar.checkbox("Use LLM", value=False, help="Checking this box uses an LLM "
                                                                  "to extract the "
                                                                  "keywords from the prompt to "
                                                                  "lookup in the database",
                                     disabled=k_queries < 1)
query_handler.kw_llm = query_handler.ALL_MODELS[
    st.sidebar.selectbox("KeyLLM Model", query_handler.ALL_MODELS.keys(), index=0,
                         help="Choose the LLM model to extract keywords from the prompt",
                         disabled=k_queries < 1 or not use_llm_for_kw)]

mix = st.sidebar.slider("Mix Keyword and Similarity", 0.0, 1.0, 0.5, 0.1,
                        help="Mix the keyword search and similarity search results. 0.0 means only keyword search "
                             "results and 1.0 means only similarity search results",
                        disabled=k_queries < 1 or not (use_keybert or use_llm_for_kw))

remove_irrelevant = st.sidebar.checkbox("Filter Irrelevant", value=True, help="Checking this box filters the "
                                                                              "queries based on relevance",
                                        disabled=k_queries < 1)

clear_button = st.sidebar.button("Clear Conversation", key="clear")

# Load the model
query_handler.model_handler.load_model(model_name, query_handler.ALL_MODELS[model_name])

# reset everything
if clear_button:
    st.session_state['generated'] = []
    st.session_state['past'] = []
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    st.session_state['model_name'] = []


# generate a response
def generate_response(prompt, query_model_name, k, keybert, keyllm, filter_irrelevant):
    st.session_state['messages'].append({"role": "user", "content": prompt})

    response, sources = query_handler.query(query_text=prompt, model_name=query_model_name, k=k, use_keybert=keybert,
                                            use_llm_for_kw=keyllm, filter_irrelevant=filter_irrelevant)

    if sources:
        response += "\n\nSources🔬 : " + ', '.join(
            [f"{index}.{source}" for index, source in enumerate(sources, start=1)])
    elif k == 0:
        response += "\n\n🐣Using Previous Context"
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
                                   keyllm=use_llm_for_kw, filter_irrelevant=remove_irrelevant)
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(output)

if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user', avatar_style='lorelei',
                    seed='Leo')
            message(st.session_state["generated"][i], key=str(i), avatar_style='lorelei-neutral', seed='Molly')

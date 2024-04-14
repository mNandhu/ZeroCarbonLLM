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

st.sidebar.title("Sidebar")
model_name = st.sidebar.radio("Choose a model:", ("HuggingFace/zephyr-7b-beta", "gemini-1.0-pro"))
clear_button = st.sidebar.button("Clear Conversation", key="clear")

if model_name == "HuggingFace/zephyr-7b-beta":
    print("\n\nUsing HuggingFace model")
    model = query_data.setup("HuggingFace")
elif model_name == "gemini-1.0-pro":
    print("\n\nUsing Gemini model")
    model = query_data.setup("gemini-1.0-pro")
else:
    raise ValueError("Invalid model name")

# reset everything
if clear_button:
    st.session_state['generated'] = []
    st.session_state['past'] = []
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    st.session_state['model_name'] = []


# generate a response
def generate_response(prompt, query_model):
    st.session_state['messages'].append({"role": "user", "content": prompt})

    response, sources = query_data.query(prompt, query_model)

    if sources:
        response += "\n\nSources : " + ', '.join(
            [f"{index}.{source}" for index, source in enumerate(sources, start=1)])

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
        output = generate_response(user_input, model)
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(output)

if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
            message(st.session_state["generated"][i], key=str(i))

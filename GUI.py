import streamlit as st
from streamlit_chat import message
import query_data

db, model = query_data.setup()

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
message("""\
Hi, I am ZeroCarbonLLM. I am here to help you with your queries.\
You can ask me anything related to Carbon Capture.\
Currently, I am trained on a small dataset, so I may not be able to answer all your questions.\
Please ask your questions in a clear and concise manner.\
As of now, I can answer only one question at a time, and have a very short-term memory.""", key='0_startup')


# generate a response
def generate_response(prompt, database, query_model):
    st.session_state['messages'].append({"role": "user", "content": prompt})

    response, sources = query_data.query(prompt, database, query_model)

    if sources:
        response += "\nSources : " + ','.join(sources)
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
        output = generate_response(user_input, db, model)
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(output)

if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
            message(st.session_state["generated"][i], key=str(i))

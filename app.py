"""Streamlit entry point for the project."""

import streamlit as st

st.set_page_config(page_title="Python Docs Assistant", page_icon="🐍")

st.title("Python Docs Assistant")
st.caption("An agentic RAG prototype for the Python standard library")
st.info("Project skeleton: question answering is not available yet.")

st.subheader("What this assistant will do")
st.markdown(
    """
    - Search a curated collection of Python documentation.
    - Use a LangGraph workflow to select and execute subtasks.
    - Show retrieved sources and the steps taken to answer a question.
    """
)
st.write("Next: prepare the documentation corpus and retrieval index.")
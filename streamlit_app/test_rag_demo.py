"""
Test script for RAG Demo functionality
"""

import streamlit as st

# Page config
st.set_page_config(page_title="RAG Demo Test", page_icon="🔍", layout="wide")

st.title("🔍 Test RAG Demo")

# Test basic functionality
query = st.text_area("Enter query:", height=100)

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Generate Answer", type="primary"):
        if query:
            with st.spinner("Processing..."):
                import time

                time.sleep(1)

                st.success("✅ Query processed successfully!")

                # Display mock answer
                st.markdown("### Answer")
                st.info(
                    f"""
                This is a test response for your query: "{query}"

                The system is working correctly and can process queries.
                """
                )

                # Display mock metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Response Time", "1.5s")
                with col2:
                    st.metric("Confidence", "0.89")
                with col3:
                    st.metric("Citations", "2")
        else:
            st.warning("Please enter a query!")

with col2:
    if st.button("🧹 Clear"):
        st.rerun()

# Test session state
if "counter" not in st.session_state:
    st.session_state.counter = 0

if st.button("Test Counter"):
    st.session_state.counter += 1
    st.write(f"Counter: {st.session_state.counter}")

st.info(
    "If you can see this page and click buttons, basic Streamlit functionality is working!"
)

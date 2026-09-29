import streamlit as st
# Import your local execution script
from main_locally import run_job_hunter

st.set_page_config(page_title="Job Hunter Agent", layout="wide")
st.title("Job Hunter Agent Dashboard")

# ---------------------------------------------------------
# 1. INPUT DATA SECTION
# ---------------------------------------------------------
st.sidebar.header("Agent Parameters")

# File upload input
uploaded_cv = st.sidebar.file_uploader("Upload Your CV (PDF)", type=["pdf"])

# Text & slider inputs
keywords = st.sidebar.text_input("main roles ('default' = ML/Data Eng.)")
location = st.sidebar.text_input("Location")
min_score = st.sidebar.slider("Minimum Match Score", min_value=1, max_value=10, value=6)

# Model choice input
model_choice = st.sidebar.selectbox(
    "Ollama Model", 
    ["qwen2.5-coder:7b", "llama3.2:3b", "deepseek-r1:7b"]
)

# Execution trigger button
run_agent = st.button("▶ Run Job Search Pipeline", type="primary")

# ---------------------------------------------------------
# 2. OUTPUT DATA SECTION
# ---------------------------------------------------------
if run_agent:
    if not uploaded_cv:
        st.warning("Please upload a CV first.")
    else:
        with st.spinner("Fetching jobs and evaluating with Ollama..."):
            # Save uploaded PDF temporarily for parsing
            with open("temp_cv.pdf", "wb") as f:
                f.write(uploaded_cv.getbuffer())

            # Call your Python agent logic
            results = run_job_hunter(
                cv_path="temp_cv.pdf",
                location=location,
                search_terms=keywords,
                threshold=min_score,
                model_name=model_choice
            )

        st.success("Evaluation complete!")

        # Output Metric Summary
        st.metric(label="Matching Jobs Found", value=len(results))

        # Output Detailed Cards / Tables
        for job in results:
            score = job.get("match_score", 0)
            title = job.get("title", "Unknown Role")
            company = job.get("company", "Unknown Company")
            
            with st.expander(f"[{score}/10] {title} - {company}"):
                st.write(f"**Location:** {job.get('location', 'Remote')}")
                st.write(f"**Fit Reason:** {job.get('summary', 'No summary provided.')}")
                st.markdown(f"[Apply Here]({job.get('application_url', '#')})")
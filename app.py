import os
import re
import json
import subprocess
import streamlit as st
from dotenv import load_dotenv
from langchain import PromptTemplate, LLMChain
from langchain_groq import ChatGroq

# ------------------------- Setup -------------------------
load_dotenv()
st.set_page_config(page_title="Unit Test Generator", layout="wide")
st.title("🧪 Generate & Check Pytest Tests from README")

# --- LangChain / Groq ---
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
llm = ChatGroq(model="qwen/qwen3-32b", temperature=0.2)

# --------------------- Prompt Template -------------------
prompt_template = """
You are an AI that generates Python pytest test files.

TASK:
- Read the README below.
- Write a single Python file named `test_generated.py`.
- If described functions do not exist, create placeholder implementations inside it.
- Then write exactly {num_tests} pytest test functions.
- Return ONLY valid Python code between:
<PYTEST_FILE>
# your code here
</PYTEST_FILE>

❌ No markdown
❌ No explanations
❌ No <think> or reasoning text
✅ Only valid, executable Python code

README:
{readme_content}
"""

prompt = PromptTemplate(
    input_variables=["readme_content", "num_tests"],
    template=prompt_template,
)
chain = LLMChain(llm=llm, prompt=prompt)

# --------------------- Helpers ---------------------------
def extract_code(raw: str) -> str:
    """Clean the LLM output and extract pure Python code."""
    if not raw:
        return ""

    # Remove any hidden reasoning, think blocks, markdown fences
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"```(?:python)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```", "", raw)
    raw = raw.strip()

    # Extract between PYTEST_FILE tags if present
    match = re.search(r"<PYTEST_FILE>([\s\S]*?)</PYTEST_FILE>", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Otherwise return the cleaned text block
    return raw.strip()

def run_pytest_json(test_file: str, timeout_sec: int = 60):
    """Run pytest and parse JSON report."""
    cmd = ["pytest", test_file, "--disable-warnings", "--maxfail=10", "--json-report", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    report = None
    if os.path.exists(".report.json"):
        with open(".report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
    return (proc.returncode == 0, report, proc.stdout, proc.stderr)

def show_summary(report: dict, stdout: str, stderr: str):
    """Display pytest summary nicely."""
    st.subheader("📊 Pytest Results")
    tests = report.get("tests", []) if report else []
    summary = report.get("summary", {}) if report else {}

    collected = summary.get("collected", len(tests))
    passed = summary.get("passed", sum(1 for t in tests if t.get("outcome") == "passed"))
    failed = summary.get("failed", sum(1 for t in tests if t.get("outcome") == "failed"))
    errors = summary.get("errors", 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.info(f"Collected: **{collected}**")
    col2.success(f"Passed: **{passed}**")
    col3.error(f"Failed: **{failed}**")
    col4.warning(f"Errors: **{errors}**")

    st.divider()
    for t in tests:
        nodeid = t.get("nodeid", "")
        outcome = t.get("outcome", "")
        if outcome == "passed":
            st.success(f"✅ {nodeid}")
        elif outcome == "failed":
            st.error(f"❌ {nodeid}")
            if t.get("longrepr"):
                st.code(t["longrepr"], language="bash")

    if stdout:
        st.subheader("🧾 Pytest Output")
        st.code(stdout, language="bash")
    if stderr:
        st.subheader("⚠️ Pytest Errors")
        st.code(stderr, language="bash")

# ----------------------- Streamlit UI ----------------------
st.markdown("Upload a README, select number of tests, then generate.")

left, right = st.columns([2, 1])
with right:
    num_tests = st.slider("Number of tests", 3, 8, 4)
    run_button_label = "🚀 Generate tests & Run pytest"

uploaded_file = left.file_uploader("Upload README.md", type=["md", "txt"])

if uploaded_file:
    readme_content = uploaded_file.read().decode("utf-8", errors="ignore")
    with st.expander("📄 README Preview", expanded=True):
        st.code(readme_content, language="markdown")

    if st.button(run_button_label, type="primary"):
        with st.spinner("Generating tests with the LLM..."):
            try:
                raw_response = chain.run(
                    readme_content=readme_content,
                    num_tests=num_tests,
                )
            except Exception as e:
                st.error(f"LLM generation error: {e}")
                st.stop()

        code = extract_code(raw_response)
        if not code.strip():
            st.error("❌ No valid Python code extracted.")
            st.code(raw_response)
            st.stop()

        with open("test_generated.py", "w", encoding="utf-8") as f:
            f.write(code)

        st.subheader("📝 Generated `test_generated.py`")
        st.code(code, language="python")

        with st.spinner("Running pytest..."):
            try:
                ok, report, stdout, stderr = run_pytest_json("test_generated.py", 90)
            except subprocess.TimeoutExpired:
                st.error("❌ Pytest timed out (90s).")
                st.stop()
            except Exception as e:
                st.error(f"Unexpected error: {e}")
                st.stop()

        if report:
            show_summary(report, stdout, stderr)
        else:
            st.error("❌ No pytest report generated.")
            if stdout:
                st.code(stdout, language="bash")
else:
    st.info("⬆️ Upload a README to start.")

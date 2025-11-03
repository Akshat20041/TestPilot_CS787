import os
import re
import json
import subprocess
import streamlit as st
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_groq import ChatGroq

# ----------------------------------------------------------
# Setup
# ----------------------------------------------------------
load_dotenv()
st.set_page_config(page_title="🧪 Generate & Check Pytest Tests", layout="wide")
st.title("🧪 Generate & Check Pytest Tests from README")

os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0.2)

# ----------------------------------------------------------
# Prompt template
# ----------------------------------------------------------
template = """
You are an AI that writes Python pytest files.

TASK:
- Read the README below.
- Generate a Python file named `test_generated.py` implementing exactly {num_tests} pytest functions.
- If the described functions don't exist, create minimal placeholder implementations.
- Output *only* valid Python code between the tags:
<PYTEST_FILE>
# your code here
</PYTEST_FILE>

No explanations, no markdown, no reasoning, no <think> text — just the code.
README:
{readme_content}
"""

prompt = PromptTemplate.from_template(template)
chain = LLMChain(prompt=prompt, llm=llm)

# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------
def extract_code(raw: str) -> str:
    """Strip reasoning & extract code from model output."""
    raw = re.sub(r"<think>.*?</think>", "", str(raw), flags=re.DOTALL)
    match = re.search(r"<PYTEST_FILE>([\s\S]*?)</PYTEST_FILE>", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    blocks = re.findall(r"```(?:python)?([\s\S]*?)```", raw)
    if blocks:
        return blocks[0].strip()
    return raw.strip()


def run_pytest_json(test_file: str, timeout: int = 60):
    cmd = ["pytest", test_file, "--disable-warnings", "--maxfail=10", "--json-report", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    report = None
    if os.path.exists(".report.json"):
        try:
            with open(".report.json", "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            pass
    return (proc.returncode == 0, report, proc.stdout, proc.stderr)


def show_summary(report: dict, stdout: str, stderr: str):
    st.subheader("📊 Pytest Summary")
    tests = report.get("tests", []) if report else []
    summary = report.get("summary", {}) if report else {}

    collected = summary.get("collected", len(tests))
    passed = summary.get("passed", sum(1 for t in tests if t.get("outcome") == "passed"))
    failed = summary.get("failed", sum(1 for t in tests if t.get("outcome") == "failed"))
    errors = summary.get("errors", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.info(f"Collected: **{collected}**")
    c2.success(f"Passed: **{passed}**")
    c3.error(f"Failed: **{failed}**")
    c4.warning(f"Errors: **{errors}**")

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
        st.subheader("🧾 Stdout")
        st.code(stdout, language="bash")
    if stderr:
        st.subheader("⚠️ Stderr")
        st.code(stderr, language="bash")


# ----------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------
st.markdown("Upload a README → choose #tests → generate & run Pytest.")

col1, col2 = st.columns([2, 1])
with col2:
    num_tests = st.slider("Number of tests", 3, 8, 4)
    go = st.button("🚀 Generate & Run Tests", type="primary")

uploaded = col1.file_uploader("Upload README.md / .txt", type=["md", "txt"])

if uploaded:
    readme = uploaded.read().decode("utf-8", errors="ignore")
    with st.expander("📄 README Preview", expanded=True):
        st.code(readme, language="markdown")

    if go:
        with st.spinner("Generating code..."):
            try:
                result = chain.run(readme_content=readme, num_tests=num_tests)
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        code = extract_code(result)
        if not code.strip():
            st.error("❌ No code generated.")
            st.code(result)
            st.stop()

        if "def test_" not in code:
            st.warning("⚠️ No pytest functions detected.")
            st.code(code, language="python")
            st.stop()

        with open("test_generated.py", "w", encoding="utf-8") as f:
            f.write(code)

        st.subheader("📝 Generated File")
        st.code(code, language="python")

        with st.spinner("Running pytest..."):
            try:
                ok, report, stdout, stderr = run_pytest_json("test_generated.py", 90)
            except subprocess.TimeoutExpired:
                st.error("❌ Pytest timed out (90 s)")
                st.stop()

        if report:
            show_summary(report, stdout, stderr)
        else:
            st.error("❌ No pytest report.")
            if stdout:
                st.code(stdout, language="bash")
else:
    st.info("⬆️ Upload a README to begin.")

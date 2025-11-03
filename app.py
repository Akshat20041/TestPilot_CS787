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

# --- LLM Setup ---
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0.2)

# --------------------- Prompt Template -------------------
template = """
You are an AI that generates Python pytest test files.

Task:
- Given the README content below, write a single Python file named `test_generated.py`.
- If the described functions do not exist, create simple placeholder implementations inside the same file.
- Then write ONLY {num_tests} pytest test functions that validate the described functionality.
- Output your result inside <PYTEST_FILE>...</PYTEST_FILE> tags.
- Output ONLY valid Python code. No markdown, no explanations.

README CONTENT:
{readme_content}
"""

prompt = PromptTemplate(
    input_variables=["readme_content", "num_tests"],
    template=template,
)

chain = LLMChain(prompt=prompt, llm=llm)

# --------------------- Helper Functions -------------------
def extract_code(raw: str) -> str:
    """Extract code between <PYTEST_FILE> tags."""
    match = re.search(r"<PYTEST_FILE>([\s\S]*?)</PYTEST_FILE>", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    blocks = re.findall(r"```(?:python)?([\s\S]*?)```", raw)
    if blocks:
        return blocks[0].strip()
    return raw.strip()


def run_pytest_json(test_file: str, timeout_sec: int = 60):
    """Run pytest with JSON report; returns (exit_ok, report_dict, stdout, stderr)."""
    cmd = ["pytest", test_file, "--disable-warnings", "--maxfail=10", "--json-report", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    report_path = ".report.json"
    report = None
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            report = None
    return (proc.returncode == 0, report, proc.stdout, proc.stderr)


def show_summary(report: dict, stdout: str, stderr: str):
    """Display pytest summary in Streamlit."""
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
    if tests:
        st.subheader("🔍 Test Details")
        for t in tests:
            nodeid = t.get("nodeid", "unknown_test")
            outcome = t.get("outcome", "unknown")
            if outcome == "passed":
                st.success(f"✅ {nodeid}")
            elif outcome == "failed":
                st.error(f"❌ {nodeid}")
                longrepr = t.get("longrepr", "")
                if longrepr:
                    st.code(longrepr, language="bash")

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
        with st.spinner("Generating test file using LLM..."):
            try:
                result = chain.run(
                    readme_content=readme_content, num_tests=num_tests
                )
            except Exception as e:
                st.error(f"Error during generation: {e}")
                st.stop()

        code = extract_code(result)
        if "def test_" not in code:
            st.error("No test_ functions detected in generated code.")
            st.code(code, language="python")
            st.stop()

        with open("test_generated.py", "w", encoding="utf-8") as f:
            f.write(code)

        st.subheader("📝 Generated test_generated.py")
        st.code(code, language="python")

        with st.spinner("Running pytest..."):
            try:
                ok, report, stdout, stderr = run_pytest_json("test_generated.py", 90)
            except subprocess.TimeoutExpired:
                st.error("Pytest timed out (90s).")
                st.stop()
            except Exception as e:
                st.error(f"Pytest execution failed: {e}")
                st.stop()

        if report:
            show_summary(report, stdout, stderr)
        else:
            st.error("No report generated.")
            if stdout:
                st.code(stdout, language="bash")
else:
    st.info("⬆️ Upload a README to start.")

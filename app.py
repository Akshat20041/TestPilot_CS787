import os
import re
import json
import subprocess
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# ------------------------- Setup -------------------------
load_dotenv()
st.set_page_config(page_title="Unit Test Generator", layout="wide")
st.title("Generate & Check Pytest Tests from README")

# LangChain / Groq
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
llm = ChatGroq(model="qwen/qwen3-32b")  # you can switch models here

# --------------------- Prompt Template -------------------
prompt_template = """
You are an AI that generates Python pytest test files.

Task:
- Given the README content below, write a single Python file named `test_generated.py`.
- If the described functions do not exist, create simple placeholder implementations inside the same file.
- Then write ONLY {num_tests} pytest test functions that validate the described functionality.
- Output ONLY valid Python code. No markdown, no explanations, no comments.

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
    """Extract code inside <PYTEST_FILE>...</PYTEST_FILE>, else fallback to ```python``` blocks."""
    m = re.search(r"<PYTEST_FILE>([\s\S]*?)</PYTEST_FILE>", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    if blocks:
        return max(blocks, key=len).strip()
    return raw.strip()

def keep_at_most_n_tests(code: str, n: int) -> str:
    """Keep imports/header + first n test functions."""
    first_test = re.search(r"^\s*def\s+test_", code, flags=re.M)
    if not first_test:
        return code
    header = code[: first_test.start()]
    body = code[first_test.start():]
    pattern = re.compile(r"(^\s*def\s+test_[\s\S]*?)(?=^\s*def\s+test_|\Z)", re.M)
    tests = pattern.findall(body)
    trimmed = "".join(tests[:n])
    return header + trimmed

def ensure_min_tests(code: str, min_tests: int) -> int:
    return len(re.findall(r"^\s*def\s+test_", code, flags=re.M))

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
    st.subheader("📊 Pytest Results")
    tests = report.get("tests", []) if report else []
    summary = report.get("summary", {}) if report else {}

    collected = summary.get("collected", len(tests))
    passed = summary.get("passed", sum(1 for t in tests if t.get("outcome") == "passed"))
    failed = summary.get("failed", sum(1 for t in tests if t.get("outcome") == "failed"))
    errors = summary.get("errors", summary.get("xpassed", 0))

    col1, col2, col3, col4 = st.columns(4)
    col1.info(f"Collected: **{collected}**")
    col2.success(f"Passed: **{passed}**")
    col3.error(f"Failed: **{failed}**")
    col4.warning(f"Errors: **{errors}**")

    st.divider()
    st.subheader("🔍 Per-test details")
    if tests:
        for t in tests:
            nodeid = t.get("nodeid", "unknown_test")
            outcome = t.get("outcome", "unknown")
            longrepr = t.get("longrepr", "")
            if outcome == "passed":
                st.success(f"✅ {nodeid} — PASSED")
            elif outcome == "failed":
                st.error(f"❌ {nodeid} — FAILED")
                if longrepr:
                    st.code(longrepr, language="bash")
            else:
                st.warning(f"⚠️ {nodeid} — {outcome}")

    if (not tests) or (failed == 0 and passed == 0):
        st.subheader("🧾 Raw Pytest Output")
        if stdout:
            st.code(stdout, language="bash")
        if stderr:
            st.code(stderr, language="bash")

# ----------------------- UI ------------------------------
st.markdown("Upload a `README.md`, choose number of tests, then generate.")

left, right = st.columns([2, 1])
with right:
    num_tests = st.slider("Number of tests", min_value=3, max_value=5, value=4, step=1)
    run_button_label = "🚀 Generate tests & Run pytest"

uploaded_file = left.file_uploader("Upload README.md", type=["md", "txt"])

if uploaded_file:
    readme_content = uploaded_file.read().decode("utf-8", errors="ignore")
    with st.expander("📄 README Preview", expanded=True):
        st.markdown(f"```markdown\n{readme_content}\n```")

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
        code = keep_at_most_n_tests(code, n=num_tests)

        actual = ensure_min_tests(code, min_tests=num_tests)
        if actual == 0:
            st.error("No `test_` functions detected in the generated code. Showing raw model output for debugging:")
            st.code(raw_response, language="text")

        test_path = "test_generated.py"
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(code)

        st.subheader("📝 Generated `test_generated.py`")
        st.code(code, language="python")

        with st.spinner("Running pytest..."):
            try:
                ok, report, stdout, stderr = run_pytest_json(test_path, timeout_sec=90)
            except FileNotFoundError:
                st.error("`pytest` or `pytest-json-report` not installed. Install with:\n\n`pip install pytest pytest-json-report`")
                st.stop()
            except subprocess.TimeoutExpired:
                st.error("Pytest timed out (90s). Your tests may hang or be too slow.")
                st.stop()
            except Exception as e:
                st.error(f"Unexpected error while running pytest: {e}")
                st.stop()

        if report is None:
            st.error("Pytest did not produce a JSON report. Showing raw output:")
            if stdout:
                st.code(stdout, language="bash")
            if stderr:
                st.code(stderr, language="bash")
        else:
            show_summary(report, stdout, stderr)
else:
    st.info("Upload a README to begin.")

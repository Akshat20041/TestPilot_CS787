import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# ------------------------- Setup -------------------------
load_dotenv()

# --- LangChain / Groq ---
# Make sure to set GROQ_API_KEY in your .env file
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")

llm_generator = ChatGroq(model="qwen/qwen3-32b", temperature=0.2)
llm_critic = ChatGroq(model="openai/gpt-oss-20b", temperature=0.1)
llm_reporter = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
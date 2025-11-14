import os
import json
import glob
import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

def load_examples_from_folder(examples_dir: str = "examples") -> list:
    """Load all example JSON files from the examples directory."""
    examples = []
    
    if not os.path.exists(examples_dir):
        return examples
    
    for json_file in glob.glob(f"{examples_dir}/**/*.json", recursive=True):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                example = json.load(f)
                examples.append(example)
        except Exception as e:
            st.sidebar.warning(f"Could not load {os.path.basename(json_file)}: {str(e)[:50]}")
    
    return examples

def create_vector_store(examples: list):
    """Create FAISS vector store from examples."""
    if not examples:
        return None
    
    documents = []
    for ex in examples:
        # Combine all fields for better retrieval
        text = f"Framework: {ex.get('framework', 'generic')}\n"
        text += f"Error Pattern: {ex.get('error_pattern', '')}\n"
        text += f"Error Example: {ex.get('error_example', '')}\n"
        text += f"Solution: {ex.get('solution', '')}\n"
        text += f"Fix Pattern: {ex.get('fix_pattern', '')}\n"
        text += f"Code Before:\n{ex.get('code_before', '')}\n"
        text += f"Code After:\n{ex.get('code_after', '')}\n"
        documents.append(text)
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(documents, embeddings)
    
    return vectorstore

def generate_example_template():
    """Generate a template JSON for creating new examples."""
    template = {
        "error_pattern": "Description of the error pattern (e.g., 'fixture not found')",
        "framework": "flask | fastapi | django | generic",
        "error_example": "Actual error message from pytest",
        "solution": "Explanation of how to fix the error",
        "fix_pattern": "Pattern for the fix",
        "code_before": "Example code that causes the error",
        "code_after": "Fixed code example"
    }
    return json.dumps(template, indent=2)
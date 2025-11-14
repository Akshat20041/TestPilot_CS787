def get_troubleshooting_hints(failed_tests: list, framework: str, vectorstore) -> str:
    """Retrieve relevant troubleshooting hints from knowledge base."""
    if not vectorstore or not failed_tests:
        return ""
    
    # Combine all error messages for better retrieval
    error_summary = "\n".join([
        f"{test['name']}: {test['error'][:200]}" 
        for test in failed_tests[:3]
    ])
    
    query = f"Framework: {framework}\nErrors:\n{error_summary}"
    
    try:
        # Retrieve relevant examples
        relevant_docs = vectorstore.similarity_search(query, k=2)
        
        if not relevant_docs:
            return ""
        
        hints = "\n\n🔍 SIMILAR ERROR PATTERNS FROM KNOWLEDGE BASE:\n"
        for i, doc in enumerate(relevant_docs, 1):
            hints += f"\nPattern {i}:\n{doc.page_content[:400]}\n"
        
        return hints
    except Exception as e:
        return ""

def detect_framework(user_code: str) -> str:
    """Detect if code uses Flask, Django, FastAPI, etc."""
    code_lower = user_code.lower()
    
    if 'from flask import' in code_lower or 'import flask' in code_lower:
        return 'flask'
    elif 'from django' in code_lower or 'import django' in code_lower:
        return 'django'
    elif 'from fastapi import' in code_lower or 'import fastapi' in code_lower:
        return 'fastapi'
    else:
        return 'generic'

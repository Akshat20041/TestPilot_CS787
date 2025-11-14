import re
import ast

def extract_functions_from_readme(readme: str) -> list:
    """Extract function names from README using multiple patterns."""
    functions = []
    
    # Pattern 1: def function_name( in code blocks
    pattern1 = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    functions.extend(re.findall(pattern1, readme))
    
    # Pattern 2: function_name(self) in method signatures
    pattern2 = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(self'
    functions.extend(re.findall(pattern2, readme))
    
    # Pattern 3: `function_name()` or `function_name(args)`
    pattern3 = r'`([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)`'
    functions.extend(re.findall(pattern3, readme))
    
    # Pattern 4: ### function_name(args) or ### function_name - headers with function calls
    pattern4 = r'###\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    functions.extend(re.findall(pattern4, readme))
    
    # Pattern 5: function_name(args) at start of line (not in code blocks)
    pattern5 = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)(?:\s*$|\s*[-:])'
    functions.extend(re.findall(pattern5, readme, re.MULTILINE))
    
    # Pattern 6: **function_name(args)** in bold
    pattern6 = r'\*\*([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\*\*'
    functions.extend(re.findall(pattern6, readme))
    
    # Pattern 7: - function_name(args) in lists
    pattern7 = r'[-•]\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    functions.extend(re.findall(pattern7, readme))
    
    # Pattern 8: Flask routes like GET /items - function_name()
    pattern8 = r'[-•]\s*`[A-Z]+\s+/[^`]*`.*?[-–—]\s*`?([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    functions.extend(re.findall(pattern8, readme))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_functions = []
    for func in functions:
        # Skip private methods and common non-function words
        if func not in seen and not func.startswith('_') and func.lower() not in ['module', 'key', 'class', 'object', 'property', 'input', 'output', 'returns', 'return']:
            seen.add(func)
            unique_functions.append(func)
    
    return unique_functions[:20]  # Max 20 functions

def extract_functions_from_python_file(python_code: str) -> list:
    """Extract function names directly from Python code using AST."""
    functions = []
    
    try:
        tree = ast.parse(python_code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods
                if not node.name.startswith('_'):
                    functions.append(node.name)
        
        return functions[:20]  # Max 20 functions
        
    except Exception as e:
        # Fallback to empty list if parsing fails
        return []

def extract_code(raw: str) -> str:
    """Clean the LLM output and extract pure Python code."""
    if not raw:
        return ""
    
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"```(?:python)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```", "", raw)
    raw = raw.strip()
    
    match = re.search(r"<PYTEST_FILE>([\s\S]*?)</PYTEST_FILE>", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return raw.strip()

def extract_user_functions(user_code: str, detected_function_names: list) -> str:
    """Extract only the detected functions/classes from user's code."""
    try:
        tree = ast.parse(user_code)
        extracted_items = []
        extracted_names = set()
        
        for node in ast.walk(tree):
            # Extract standalone functions
            if isinstance(node, ast.FunctionDef):
                if node.name in detected_function_names and node.name not in extracted_names:
                    func_lines = user_code.split('\n')[node.lineno-1:node.end_lineno]
                    extracted_items.append('\n'.join(func_lines))
                    extracted_names.add(node.name)
            
            # Extract entire class if any method matches
            elif isinstance(node, ast.ClassDef):
                class_has_target_method = False
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name in detected_function_names:
                        class_has_target_method = True
                        break
                
                if class_has_target_method and node.name not in extracted_names:
                    class_lines = user_code.split('\n')[node.lineno-1:node.end_lineno]
                    extracted_items.append('\n'.join(class_lines))
                    extracted_names.add(node.name)
        
        if extracted_items:
            result = '\n\n'.join(extracted_items)
            # Keep essential imports that don't reference external packages
            essential_imports = []
            for line in user_code.split('\n'):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    # Only keep standard library imports
                    if not any(pkg in line for pkg in ['requests', 'urllib3', 'chardet', 'idna']):
                        essential_imports.append(line)
            
            if essential_imports:
                return '\n'.join(essential_imports) + '\n\n' + result
            return result
        else:
            return user_code
            
    except Exception as e:
        return user_code

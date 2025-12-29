
import re
from pathlib import Path

def sanitize():
    toml_path = Path('pyproject.toml')
    
    with open(toml_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    removed_count = 0
    
    for line in lines:
        # Check if line is a dependency with a marker (contains ';')
        # Only target lines inside the dependencies array?
        # The file is mostly dependencies.
        # Markers usually strictly look like `package... ; marker`
        if ';' in line and ('==' in line or '>=' in line):
            print(f"Removing marked dependency: {line.strip()}")
            removed_count += 1
            continue
            
        new_lines.append(line)
        
    with open(toml_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    print(f"Sanitized {removed_count} dependencies.")

if __name__ == "__main__":
    sanitize()

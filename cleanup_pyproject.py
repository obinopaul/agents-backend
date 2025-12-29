
import re
from pathlib import Path

def cleanup():
    toml_path = Path('pyproject.toml')
    
    with open(toml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract dependencies block
    match = re.search(r'(?m)^dependencies\s*=\s*\[([\s\S]*?)^\]', content)
    if not match:
        print("Could not find dependencies block")
        return

    deps_str = match.group(1)
    deps_list = []
    
    # Process lines
    for line in deps_str.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Safely extract string content
        # Matches: "content", or 'content',
        # Group 1 is content.
        m_str = re.match(r'^["\'](.*)["\'],?$', line)
        if m_str:
            clean_line = m_str.group(1)
            if clean_line:
                deps_list.append(clean_line)
        else:
            # Maybe line is just "package==1.0" without comma?
            clean_line = line.strip(',').strip('"').strip("'")
            if clean_line:
                deps_list.append(clean_line)
    
    # Deduplicate and Filter
    unique_deps = {}
    
    # List of low-level libs to unpin (let uv resolve)
    blacklist = {
        'google-api-core', 'googleapis-common-protos', 'proto-plus', 'protobuf',
        'grpcio', 'grpcio-status', 'google-crc32c'
    }

    for dep in deps_list:
        # split name and spec
        # Regex: starts with name, then operators or markers or end
        # Name: alphanumeric, dot, dash, underscore
        m_dep = re.match(r'^([a-zA-Z0-9\-_]+)(.*)', dep)
        if not m_dep:
            continue
            
        name = m_dep.group(1).lower()
        
        if name in blacklist:
            continue
            
        # Deduplication logic
        if name not in unique_deps:
            unique_deps[name] = dep
        else:
            current = unique_deps[name]
            # If current is loose (>=) and new is strict (==), take new.
            if '==' in dep and '==' not in current:
                unique_deps[name] = dep
            elif '==' in current and '==' not in dep:
                pass # Keep current strict pin
            else:
                unique_deps[name] = dep # Last writer wins
                
    # Reconstruct list
    new_deps = []
    for dep in sorted(unique_deps.values()):
        # Ensure we write valid TOML strings
        # If dep contains double quotes, use single quotes, etc.
        # But requirements.txt content usually is safe for double quotes unless it has them.
        # Markers use single quotes usually.
        # So wrapping in double quotes is safe.
        new_deps.append(f'    "{dep}",')
        
    new_deps_block = "dependencies = [\n" + "\n".join(new_deps) + "\n]"
    
    new_content = re.sub(r'(?m)^dependencies\s*=\s*\[([\s\S]*?)^\]', new_deps_block, content)
    
    with open(toml_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Cleaned up dependencies. Count: {len(new_deps)}")

if __name__ == "__main__":
    cleanup()

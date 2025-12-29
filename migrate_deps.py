
import re
from pathlib import Path

def migrate():
    req_path = Path('requirements.txt')
    toml_path = Path('pyproject.toml')
    
    if not req_path.exists():
        print("requirements.txt not found")
        return

    # Read requirements.txt
    dependencies = []
    with open(req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-e'):
                continue
            
            # Remove inline comments (e.g., "package==1.0 # comment")
            # We must be careful not to split URLs (though pkg requirements usually don't have URLs with #)
            pkg_spec = line.split('#')[0].strip()
            
            # Clean up potential trailing semicolons if they are not part of markers
            # But PEP 508 markers use semicolons. e.g. "name; os_name=='linux'"
            # We keep the semicolon.
            
            if pkg_spec:
                # formatting for TOML array
                dependencies.append(f'    "{pkg_spec}",')

    # Read pyproject.toml
    with open(toml_path, 'r', encoding='utf-8') as f:
        toml_content = f.read()

    # Reconstruct the dependencies list safely
    new_deps_block = "dependencies = [\n" + "\n".join(dependencies) + "\n]"
    
    # Use a customized replacement to completely replace the existing block
    # We look for `dependencies = [` and the closing `]`
    # It seems the previous regex might have been too greedy or not greedy enough or failed on nested contents
    # But for a top-level `dependencies` key, it should be robust enough if we match brackets carefully.
    
    # However, since the file just broke, let's fix the specific error.
    # The previous error was "TOML parse error".
    # I will stick to a robust regex or full replacement if possible.
    
    pattern = r'(?m)^dependencies\s*=\s*\[[\s\S]*?^\]'
    
    if re.search(pattern, toml_content):
        new_toml = re.sub(pattern, new_deps_block, toml_content)
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write(new_toml)
        print("Updated pyproject.toml with new dependencies.")
    else:
        # Fallback: if regex fails, maybe it's because I broke it in the previous run.
        # Let's try to restore the file or just append if missing (but it should be there).
        print("Could not find dependencies block to replace. Please check file manually.")

if __name__ == "__main__":
    migrate()

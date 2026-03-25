---
name: code-review
description: Systematic code review methodology. Use this skill when reviewing code changes, PRs, or doing code audits for quality, security, and best practices.
---

# Code Review Skill

A systematic approach to reviewing code for quality, security, and maintainability.

## When to Use This Skill
- User asks to "review code" or "check my code"
- Reviewing pull requests or diffs
- Code audit tasks
- Pre-deployment code checks

## Code Review Checklist

### 1. Functionality
- [ ] Does the code do what it's supposed to do?
- [ ] Are edge cases handled?
- [ ] Are error conditions handled appropriately?

### 2. Code Quality
- [ ] Is the code readable and self-documenting?
- [ ] Are variable/function names descriptive?
- [ ] Is there unnecessary code duplication?
- [ ] Is the code well-organized?

### 3. Security
- [ ] Input validation present?
- [ ] SQL injection prevention?
- [ ] XSS prevention for web code?
- [ ] Sensitive data properly handled?
- [ ] Authentication/authorization correct?

### 4. Performance
- [ ] No obvious performance issues?
- [ ] Efficient algorithms used?
- [ ] Database queries optimized?
- [ ] Appropriate caching?

### 5. Testing
- [ ] Unit tests included?
- [ ] Edge cases tested?
- [ ] Tests pass?

## Review Approach

```python
# Example: Reviewing a function
def review_function(code: str) -> dict:
    """Analyze a function for common issues."""
    issues = []
    suggestions = []
    
    # Check function length
    lines = code.strip().split('\n')
    if len(lines) > 50:
        issues.append("Function is too long (>50 lines). Consider breaking it up.")
    
    # Check for docstring
    if '"""' not in code and "'''" not in code:
        issues.append("Missing docstring. Add documentation.")
    
    # Check for bare except
    if 'except:' in code:
        issues.append("Bare except clause. Specify exception types.")
    
    # Check for hardcoded values
    import re
    if re.search(r'["\'](?:password|secret|key)["\']', code, re.I):
        issues.append("Possible hardcoded credential. Use environment variables.")
    
    return {"issues": issues, "suggestions": suggestions}
```

## Feedback Format

When providing review feedback:

1. **Start positive** - Note what's done well
2. **Be specific** - Point to exact lines/issues
3. **Explain why** - Not just what's wrong, but why it matters
4. **Suggest fixes** - Provide concrete improvements

### Example Feedback Template:
```markdown
## Code Review Summary

### ✅ What's Good
- Clear function naming
- Good error handling in X

### 🔧 Suggested Improvements
1. **Line 25**: Consider using a constant for the magic number `42`
   - Why: Improves readability and maintainability
   - Suggestion: `MAX_RETRIES = 42`

2. **Line 48**: Missing input validation
   - Why: Could cause crash on None input
   - Suggestion: Add `if value is None: return default`

### ❗ Critical Issues
1. **Security**: SQL injection vulnerability at line 67
   - Use parameterized queries instead of string formatting
```

## Common Issues to Flag
- Magic numbers without explanation
- Missing error handling
- Security vulnerabilities (injection, XSS, etc.)
- Performance anti-patterns (N+1 queries, etc.)
- Missing tests for critical paths
- Overly complex logic
- Code duplication

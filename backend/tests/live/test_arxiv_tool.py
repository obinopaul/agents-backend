"""Quick test for arxiv_search_tool."""
from backend.src.tools.academic import arxiv_search_tool
import json

print("Testing arxiv_search_tool...")
result = arxiv_search_tool.invoke({
    "query": "machine learning",
    "max_results": 2
})

data = json.loads(result)

print(f"Query: {data.get('query')}")
print(f"Total results: {data.get('total_results')}")
print()

for r in data.get("results", []):
    print(f"[{r['rank']}] {r['title'][:60]}...")
    print(f"    PDF: {r['pdf_url']}")
    authors = r.get('authors', [])[:2]
    print(f"    Authors: {', '.join(authors)}")
    print()

print("SUCCESS!")

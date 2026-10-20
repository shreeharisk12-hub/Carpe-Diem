from ddgs import DDGS
import json
import sys


def search_web(query, max_results=3):
    try:
        results = DDGS(timeout=10).text(
            query,
            region="in-en",
            safesearch="moderate",
            max_results=max_results
        )

        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", "")
            }
            for item in results
        ]

    except Exception as e:
        return {
            "error": str(e),
            "message": "Web search unavailable"
        }


if __name__ == "__main__":
    query = " ".join(sys.argv[1:])

    if not query:
        query = "latest artificial intelligence news India"

    print(json.dumps(
        search_web(query),
        indent=2,
        ensure_ascii=False
    ))

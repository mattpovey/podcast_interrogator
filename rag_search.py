#!/usr/bin/env python3

import sys
from lib_podsearch import rag_search

def main():
    if len(sys.argv) < 2:
        print("Usage: rag_search.py \"your question about history\"")
        print("Examples:")
        print("  rag_search.py \"What were the major causes of World War I?\"")
        print("  rag_search.py \"Tell me about the fall of Constantinople\"")
        return
    
    query = " ".join(sys.argv[1:])
    print(f"\nAnalyzing question: {query}")
    rag_search(query)

if __name__ == "__main__":
    main() 
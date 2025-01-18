#!/usr/bin/env python3

import os
import sys
import openai
import chromadb
from datetime import datetime
import json
import re
from config import max_tokens
from dotenv import load_dotenv
from frontend.app.config.app_settings import SEMANTIC_COLLECTION

# Load environment variables
load_dotenv('.env')

def create_chroma_client():
    """Create a ChromaDB client connected to the server."""
    return chromadb.HttpClient(
        host=os.getenv('CHROMADB_HOST', '127.0.0.1'),
        port=os.getenv('CHROMADB_PORT', '8000'),
        ssl=False
    )

def create_llm_client():
    """Create OpenAI-compatible client for SambaNova."""
    api_key = os.environ.get("SAMBANOVA_API_KEY")
    if not api_key:
        raise ValueError("SAMBANOVA_API_KEY environment variable not set")
    
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.sambanova.ai/v1",
    )

def format_date(date_str):
    """Format date string for display."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%B %d, %Y")
    except:
        return date_str

def generate_link(url, timecode):
    """Generate a link with timestamp from URL and timecode."""
    # Parse the timecode (format: HH:MM:SS,mmm)
    pattern = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    match = re.match(pattern, timecode)
    if match:
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
        # Round to nearest second
        total_seconds = round(total_seconds)
        return f"{url}#t={total_seconds}.0"
    return url

def format_sources(results):
    """Format the source information from ChromaDB results."""
    sources = []
    for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
        source = (
            f"From episode: {metadata['title']}\n"
            f"Date: {format_date(metadata['date'])}\n"
            f"Timecode: {metadata['start_timecode']} --> {metadata['end_timecode']}\n"
            f"URL: {generate_link(metadata['url'], metadata['start_timecode'])}\n"
            f"Passage: {doc}\n"
        )
        sources.append(source)
    return "\n---\n".join(sources)

def get_search_queries(query, llm_client):
    """Use LLM to generate semantic search queries based on the user's question."""
    search_prompt = f"""Given a user's history question, create TWO different semantic search queries that will help find relevant information in a podcast transcript database.
The queries should:
1. Look for different aspects of the topic
2. Use natural language
3. Be specific enough to find relevant content
4. Cover complementary aspects of the question
5. Focus on the core concepts of the question

User's question: {query}

You must respond with valid JSON in exactly this format:
{{
    "query1": "first semantic search query",
    "explanation1": "why this query will help",
    "query2": "second semantic search query",
    "explanation2": "why this query will help"
}}

Do not include any other text before or after the JSON."""

    try:
        response = llm_client.chat.completions.create(
            model=os.getenv('SEMANTIC_SEARCH_MODEL'),
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates effective semantic search queries. Always respond with valid JSON."},
                {"role": "user", "content": search_prompt}
            ],
            temperature=0.1,
            top_p=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        result = json.loads(response_text)
        
        return result
        
    except Exception as e:
        return {
            "query1": f"key events and facts about {query}",
            "explanation1": "Looking for main historical facts",
            "query2": f"analysis and significance of {query}",
            "explanation2": "Looking for historical analysis and importance"
        }

def create_prompt(original_query, context1, context2):
    """Create a prompt for the LLM using the retrieved contexts."""
    return f"""You are an expert historian tasked with answering questions about history based on content from "The Rest Is History" podcast. 
Use the information provided in BOTH contexts below to answer the question comprehensively. If the contexts don't contain enough information to fully answer the question, say so.
Be specific and cite episodes when possible. Synthesize information from both contexts when relevant.

Context 1:
{context1}

Context 2:
{context2}

Question: {original_query}

Answer: """

def perform_search(collection, query, n_results=3):
    """Perform a single semantic search and return formatted results."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    if not results['documents']:
        return "No relevant passages found."
    
    return format_sources(results)

def semantic_search(query, n_results=3, collection_name=SEMANTIC_COLLECTION):
    """Perform semantic search using ChromaDB and LLM with multiple search queries."""
    # Initialize clients
    chroma_client = create_chroma_client()
    llm_client = create_llm_client()
    
    try:
        # Get collection
        collection = chroma_client.get_collection(name=collection_name)
    except Exception as e:
        print(f"Error: Collection '{collection_name}' not found.")
        return
    
    # Get LLM-generated search queries
    search_queries = get_search_queries(query, llm_client)
    
    # Perform both searches
    context1 = perform_search(collection, search_queries['query1'], n_results)
    context2 = perform_search(collection, search_queries['query2'], n_results)
    
    if context1 == "No relevant passages found." and context2 == "No relevant passages found.":
        print("No relevant passages found for either search query.")
        return
    
    # Create combined prompt
    prompt = create_prompt(query, context1, context2)
    
    # Get LLM response
    try:
        response = llm_client.chat.completions.create(
            model=os.getenv('SAMBANOVA_MODEL'),
            messages=[
                {"role": "system", "content": "You are a knowledgeable historian who provides accurate, well-reasoned answers based on podcast content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            top_p=0.1
        )
        
        # Print the answer
        print("\nAnswer from podcast content:")
        print("=" * 80)
        print(response.choices[0].message.content)
        print("=" * 80)
        
        # Print sources
        print("\nSources from first search query:")
        print("=" * 80)
        print(context1)
        
        print("\nSources from second search query:")
        print("=" * 80)
        print(context2)
        
    except Exception as e:
        print(f"Error getting LLM response: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: search_semantic.py \"your question about history\"")
        print("Examples:")
        print("  search_semantic.py \"What were the major causes of World War I?\"")
        print("  search_semantic.py \"Tell me about the fall of Constantinople\"")
        return
    
    query = " ".join(sys.argv[1:])
    print(f"\nAnalyzing question: {query}")
    semantic_search(query)

if __name__ == "__main__":
    main() 
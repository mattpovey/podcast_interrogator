#!/usr/bin/env python3

import chromadb
from chromadb.config import Settings
import json
from chunk_transcripts import process_transcripts
import hashlib
from dotenv import load_dotenv
from frontend.app.config.app_settings import SEMANTIC_COLLECTION

# Load environment variables
load_dotenv('.env')

def create_chroma_client():
    """Create a ChromaDB client connected to the server."""
    return chromadb.HttpClient(
        host="127.0.0.1",
        port="8000"
    )

def generate_chunk_id(chunk):
    """Generate a unique ID for a chunk based on its content and metadata."""
    # Combine unique identifiers to create a stable ID
    unique_string = f"{chunk['title']}_{chunk['start_timecode']}_{chunk['end_timecode']}"
    return hashlib.sha256(unique_string.encode()).hexdigest()

def index_chunks(chunks, collection_name=SEMANTIC_COLLECTION):
    """Index chunks in ChromaDB."""
    client = create_chroma_client()
    
    # Reset collection if it exists
    try:
        client.delete_collection(name=collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except:
        pass
    
    # Create new collection
    collection = client.create_collection(name=collection_name)
    print(f"Created new collection: {collection_name}")
    
    # Prepare chunks for indexing
    documents = []
    metadatas = []
    ids = []
    
    for chunk in chunks:
        # Generate unique ID for the chunk
        chunk_id = generate_chunk_id(chunk)
        
        # Prepare metadata (everything except the text content)
        metadata = {
            'title': chunk['title'],
            'start_timecode': chunk['start_timecode'],
            'end_timecode': chunk['end_timecode'],
            'url': chunk['url'],
            'date': str(chunk['date']),  # Convert date to string for ChromaDB
            'filename': chunk['filename']
        }
        
        documents.append(chunk['text'])
        metadatas.append(metadata)
        ids.append(chunk_id)
        
        # Index in batches of 100 to avoid memory issues
        if len(documents) >= 100:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Indexed batch of {len(documents)} chunks")
            documents = []
            metadatas = []
            ids = []
    
    # Index any remaining chunks
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Indexed final batch of {len(documents)} chunks")
    
    return collection

def main():
    print("Starting semantic indexing process...")
    
    # Get chunks from transcripts
    print("Processing transcripts into chunks...")
    chunks = process_transcripts()
    print(f"Generated {len(chunks)} chunks")
    
    # Index chunks in ChromaDB
    print("\nIndexing chunks in ChromaDB...")
    collection = index_chunks(chunks)
    
    # Verify indexing
    count = collection.count()
    print(f"\nIndexing complete. Collection contains {count} chunks.")
    
    # Perform a test query
    print("\nPerforming test query...")
    results = collection.query(
        query_texts=["What is the most interesting historical event discussed?"],
        n_results=1
    )
    
    if results and results['documents']:
        print("\nSample result:")
        print(f"Text: {results['documents'][0][0][:200]}...")
        print(f"Metadata: {json.dumps(results['metadatas'][0][0], indent=2)}")

if __name__ == "__main__":
    main() 
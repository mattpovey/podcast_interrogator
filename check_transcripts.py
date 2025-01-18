#!/usr/bin/env python3

import os
import json
import srt
from datetime import datetime
import openai
from dotenv import load_dotenv
from config import tscript_dir, pod_prefix
import sys

# Load environment variables
load_dotenv('.env')

def create_llm_client():
    """Create OpenAI-compatible client for SambaNova."""
    api_key = os.getenv("SAMBANOVA_API_KEY")
    if not api_key:
        raise ValueError("SAMBANOVA_API_KEY environment variable not set")
    
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.sambanova.ai/v1",
    )

def get_episode_metadata(filename):
    """Extract metadata from the transcript filename."""
    # Expected format: YYYYMMDD_TITLE.srt
    date = filename[:8]
    title = filename[9:-4]  # Remove date prefix and .srt extension
    return {
        'date': date,
        'title': title,
        'filename': filename
    }

def check_transcript(client, transcript_text, metadata):
    """Use SambaNova API to check transcript for potential errors."""
    system_prompt = """You are an expert at identifying transcription errors in podcast transcripts. 
    Focus on identifying probable errors in proper nouns (names, places, technical terms) based on context.
    For each potential error you find:
    1. Note the exact text that may be incorrect
    2. Provide your suggested correction
    3. Explain why you believe this is an error
    4. Rate your confidence in the correction (High/Medium/Low)
    
    You MUST format your response as a valid JSON array. Each item in the array should be an object with these exact fields:
    {
        "original_text": "the text that appears incorrect",
        "suggested_correction": "your suggested correction",
        "explanation": "why you believe this is an error",
        "confidence": "High/Medium/Low"
    }
    
    If you find no errors, return an empty array: []"""

    user_prompt = f"""Review this podcast transcript segment for potential transcription errors.
    Episode Title: {metadata['title']}
    Date: {metadata['date']}
    
    Transcript text:
    {transcript_text}
    
    Return ONLY a JSON array of potential errors. Each error must have original_text, suggested_correction, explanation, and confidence fields."""

    try:
        response = client.chat.completions.create(
            model="Meta-Llama-3.1-70B-Instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )

        # Extract the response content
        content = response.choices[0].message.content.strip()
        
        # If the content is empty or just whitespace, return empty list
        if not content:
            return []
            
        # Try to parse as JSON, looking for both array and object formats
        try:
            parsed = json.loads(content)
            # If we got an object with a suggestions/errors/results key, use that
            if isinstance(parsed, dict):
                for key in ['suggestions', 'errors', 'results', 'corrections']:
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
                # If no known keys found but there's only one key and it's a list, use that
                if len(parsed) == 1 and isinstance(next(iter(parsed.values())), list):
                    return next(iter(parsed.values()))
                # Otherwise, wrap the whole object in a list
                return [parsed]
            # If we got an array directly, use that
            elif isinstance(parsed, list):
                return parsed
            # Anything else, return empty list
            return []
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response for {metadata['filename']}: {str(e)}")
            print(f"Raw response: {content}")
            return []
            
    except Exception as e:
        print(f"Error calling SambaNova API for {metadata['filename']}: {str(e)}")
        return []

def process_transcript_file(client, filepath, output_dir):
    """Process a single transcript file and generate correction suggestions."""
    filename = os.path.basename(filepath)
    metadata = get_episode_metadata(filename)
    
    print(f"Processing: {metadata['title']}")
    
    # Read and parse the SRT file
    with open(filepath, 'r') as f:
        try:
            subtitles = list(srt.parse(f))
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            return
    
    # Process the entire transcript at once
    transcript_text = "\n".join(sub.content for sub in subtitles)
    
    # Get suggestions for the transcript
    suggestions = check_transcript(client, transcript_text, metadata)
    
    # For each suggestion, find the relevant subtitle entry for timing information
    for suggestion in suggestions:
        original_text = suggestion['original_text']
        # Find the subtitle entry containing this text
        for subtitle in subtitles:
            if original_text in subtitle.content:
                suggestion['start_time'] = str(subtitle.start)
                suggestion['end_time'] = str(subtitle.end)
                break
    
    # Save suggestions if any were found
    if suggestions:
        output_file = os.path.join(output_dir, f"{filename[:-4]}_suggestions.json")
        with open(output_file, 'w') as f:
            json.dump({
                'metadata': metadata,
                'suggestions': suggestions
            }, f, indent=2)
        print(f"Found {len(suggestions)} potential corrections for {filename}")
    else:
        print(f"No corrections suggested for {filename}")

def main():
    # Create output directory
    output_dir = os.path.join(pod_prefix, "transcript_corrections")
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize SambaNova client
    client = create_llm_client()
    
    # Get list of files to process
    if len(sys.argv) > 1:
        # Process single file specified as argument
        filename = sys.argv[1]
        if not os.path.exists(os.path.join(tscript_dir, filename)):
            print(f"Error: File {filename} not found in {tscript_dir}")
            return
        files_to_process = [filename]
    else:
        # Process all .srt files
        files_to_process = [f for f in os.listdir(tscript_dir) if f.endswith('.srt')]
    
    print(f"Found {len(files_to_process)} files to process")
    
    # Process each transcript file
    for i, filename in enumerate(files_to_process, 1):
        print(f"\nProcessing file {i}/{len(files_to_process)}: {filename}")
        filepath = os.path.join(tscript_dir, filename)
        process_transcript_file(client, filepath, output_dir)

if __name__ == "__main__":
    import sys
    main() 
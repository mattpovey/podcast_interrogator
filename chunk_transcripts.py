#!/usr/bin/env python3

import os
import re
import srt
from datetime import timedelta
from libPodSemSearch import get_db_connection
from config import tscript_dir

def merge_subtitle_lines(subtitles, target_chunk_size=500, max_chunk_size=800):
    """
    Merge consecutive subtitle lines into semantic chunks while preserving timecode information.
    
    Parameters:
    - subtitles: List of SRT subtitle objects
    - target_chunk_size: Target number of characters per chunk (default: 500)
    - max_chunk_size: Maximum characters before forcing a chunk break (default: 800)
    
    Returns list of chunks with their start and end times.
    """
    chunks = []
    current_chunk = []
    current_text = []
    current_char_count = 0
    
    def create_chunk(chunk_subtitles, texts):
        """Helper function to create a chunk from collected subtitles."""
        if not chunk_subtitles:
            return None
        return {
            'text': ' '.join(texts),
            'start_time': chunk_subtitles[0].start,
            'end_time': chunk_subtitles[-1].end,
            'start_timecode': srt.timedelta_to_srt_timestamp(chunk_subtitles[0].start),
            'end_timecode': srt.timedelta_to_srt_timestamp(chunk_subtitles[-1].end)
        }
    
    for i, subtitle in enumerate(subtitles):
        current_chunk.append(subtitle)
        current_text.append(subtitle.content)
        current_char_count += len(subtitle.content)
        
        # Conditions for creating a new chunk:
        create_new_chunk = False
        
        # 1. Reached or exceeded max chunk size
        if current_char_count >= max_chunk_size:
            create_new_chunk = True
        
        # 2. Reached target size and found a good break point
        elif current_char_count >= target_chunk_size:
            # Check if current subtitle ends with sentence-ending punctuation
            if subtitle.content.rstrip()[-1] in '.!?':
                create_new_chunk = True
            # Or if there's a long pause before the next subtitle (> 2 seconds)
            elif i < len(subtitles) - 1 and (subtitles[i+1].start - subtitle.end).total_seconds() > 2:
                create_new_chunk = True
        
        # 3. Long pause between subtitles (> 4 seconds)
        elif i < len(subtitles) - 1 and (subtitles[i+1].start - subtitle.end).total_seconds() > 4:
            create_new_chunk = True
        
        if create_new_chunk:
            chunk = create_chunk(current_chunk, current_text)
            if chunk:
                chunks.append(chunk)
            current_chunk = []
            current_text = []
            current_char_count = 0
    
    # Handle any remaining subtitles
    if current_chunk:
        chunk = create_chunk(current_chunk, current_text)
        if chunk:
            chunks.append(chunk)
    
    return chunks

def process_transcripts():
    """Process all transcript files into chunks with metadata."""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    all_chunks = []
    total_chars = 0
    
    try:
        # Process each transcript file
        for filename in os.listdir(tscript_dir):
            if not filename.endswith('.srt'):
                continue
            
            # Get episode metadata from database
            cursor.execute("""
                SELECT title, description, url, date 
                FROM episodes 
                WHERE filename = %s
            """, (filename,))
            record = cursor.fetchone()
            
            if not record:
                print(f"No database record found for {filename}")
                continue
            
            title, description, url, date = record
            print(f"Processing: {title}")
            
            # Parse the SRT file
            with open(os.path.join(tscript_dir, filename), 'r') as f:
                try:
                    subtitles = list(srt.parse(f))
                except Exception as e:
                    print(f"Error parsing {filename}: {e}")
                    continue
            
            # Create chunks from the subtitles
            chunks = merge_subtitle_lines(subtitles)
            
            # Add metadata to each chunk
            for chunk in chunks:
                chunk.update({
                    'title': title,
                    'description': description,
                    'url': url,
                    'date': date,
                    'filename': filename
                })
                total_chars += len(chunk['text'])
                all_chunks.append(chunk)
            
            print(f"Created {len(chunks)} chunks from {filename}")
    
    finally:
        cursor.close()
        connection.close()
    
    # Calculate and print statistics
    if all_chunks:
        avg_chunk_size = total_chars / len(all_chunks)
        print(f"\nChunking Statistics:")
        print(f"Total chunks created: {len(all_chunks)}")
        print(f"Average chunk size: {avg_chunk_size:.1f} characters")
    
    return all_chunks

def main():
    print("Starting transcript chunking process...")
    chunks = process_transcripts()
    print(f"\nProcessed {len(chunks)} total chunks from all transcripts.")
    
    # Print a sample chunk for verification
    if chunks:
        print("\nSample chunk:")
        sample = chunks[0]
        print(f"Title: {sample['title']}")
        print(f"Time: {sample['start_timecode']} --> {sample['end_timecode']}")
        print(f"Length: {len(sample['text'])} characters")
        print(f"Text: {sample['text']}")

if __name__ == "__main__":
    main() 
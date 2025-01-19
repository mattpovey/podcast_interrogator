# Standard library imports
import os
from dotenv import load_dotenv
# Shared imports
import pandas as pd
import logging
from IPython.display import clear_output
from getpass import getpass
from tqdm import tqdm
import sys
import psycopg2
from psycopg2 import Error
import os

# Fetch to Transcript imports
import requests
import platform
from datetime import datetime
import subprocess
import glob
import feedparser

# -----------------------------------------------------------------------------
# Configure logging
# -----------------------------------------------------------------------------
logger = logging.getLogger('tscript_logger')
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# Database functions
# -----------------------------------------------------------------------------
def get_db_connection():
    """Create a database connection using environment variables."""
    load_dotenv('.env')
    try:
        connection = psycopg2.connect(
            database=os.getenv('POSTGRES_DB', 'podcast-search'),
            user=os.getenv('POSTGRES_USER', 'podsearcher'),
            password=os.getenv('POSTGRES_PASSWORD'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
        return connection
    except Error as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        raise

def setup_database():
    """Create the necessary database schema if it doesn't exist."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First, try to alter the existing table to make number nullable
        try:
            cursor.execute("""
                ALTER TABLE episodes 
                ALTER COLUMN number DROP NOT NULL;
            """)
            print("Modified 'number' column to be nullable")
            connection.commit()
        except Exception as e:
            connection.rollback()  # Rollback failed alter attempt
            print(f"Note: Could not modify 'number' column: {e}")
        
        # Create episodes table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id SERIAL PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                date DATE NOT NULL,
                number VARCHAR(4),
                description TEXT,
                filename TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        connection.commit()
        logger.info("Database schema created/updated successfully")
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error creating/updating database schema: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def add_episodes(episode_dict):
    """Add new episodes to the database, skipping existing ones."""
    new_episodes = []
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        for episode in episode_dict:
            title = episode_dict[episode]['title']
            url = episode_dict[episode]['url']
            description = episode_dict[episode]['description']
            date = episode_dict[episode]['date']
            filename = episode_dict[episode]['filename']
            
            # Check if episode exists
            cursor.execute("SELECT title FROM episodes WHERE title = %s", (title,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO episodes (title, date, description, filename, url)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (title, date, description, filename, url))
                new_episodes.append([title, date, description, filename, url])
        
        connection.commit()
        print(f'Found {len(new_episodes)} new episodes for download.')
        
        # Convert to DataFrame for compatibility with existing code
        if new_episodes:
            df_metadata = pd.DataFrame(new_episodes, columns=['title', 'date', 'description', 'filename', 'url'])
        else:
            # Get all episodes from database
            cursor.execute("SELECT title, date, description, filename, url FROM episodes ORDER BY date DESC")
            df_metadata = pd.DataFrame(cursor.fetchall(), columns=['title', 'date', 'description', 'filename', 'url'])
        
        return df_metadata
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error adding episodes to database: {e}")
        raise
    finally:
        cursor.close()
        connection.close()

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------
def check_dir(directory, count_files=0, create=0):
    if os.path.exists(directory):
        if count_files == 1:
            print("Found ", len(os.listdir(directory)), "files in", directory, ".")
            return True
        else:
            print("Found ", directory, ".")
            return True
    else:
        print("Directory ", directory, "not found.")
        if create==1:
            print("Creating directory: ", directory, ".")
            try:
                os.makedirs(directory)
                print("Directory created.")
                return True
            except:
                print("Error creating directory: ", directory, ".")
                sys.exit()

# -----------------------------------------------------------------------------
# Fetch to Transcript functions
# -----------------------------------------------------------------------------
def gen_filenames(feed):
    # Check whether the title has illegal file system name characters
    # and replace them with underscores. 
    if platform.system == 'Windows':
        illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    else:
        illegal_chars = ['/', '\\', '*', '"', '<', '>', '|']

    # Create a dictionary of episode metadata
    episode_dict = {}
    
    for episodes in feed.entries:
        # Get the title, description and URL of the podcast episode
        episode_title = episodes.title
        # Replace illegal characters in titles with underscores
        for char in illegal_chars:
            episode_title = episode_title.replace(char, '-')
        episode_description = episodes.description
        episode_url = episodes.enclosures[0].href

        # The date needs to be converted to YYYYMMDD
        episode_date = episodes.published
        date_object = datetime.strptime(episode_date, "%a, %d %b %Y %H:%M:%S %z")
        # Format the date object as YYYYMMDD
        episode_date = date_object.strftime("%Y%m%d")
        
        # Generate filename without episode number
        filename = f"{episode_date}_{episode_title}.srt"
        
        # Add the episode metadata to the episode_dict
        episode_dict[episode_title] = {
            'title': episode_title, 
            'date': episode_date, 
            'description': episode_description, 
            'url': episode_url,
            'filename': filename,
        }

    return episode_dict

def parse_feed_urls(feed_urls_str):
    """Parse comma-separated feed URLs into a list."""
    if not feed_urls_str:
        logger.error("No feed URLs provided")
        return []
    return [url.strip() for url in feed_urls_str.split(',') if url.strip()]

def consolidate_feeds(feed_urls):
    """Fetch and consolidate episodes from multiple RSS feeds."""
    all_episodes = {}
    
    for feed_url in feed_urls:
        try:
            logger.info(f"Parsing feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            episode_dict = gen_filenames(feed)
            
            # Merge episodes, avoiding duplicates based on title
            for title, episode in episode_dict.items():
                if title not in all_episodes:
                    all_episodes[title] = episode
                else:
                    # If duplicate found, keep the one with the earlier date
                    existing_date = all_episodes[title]['date']
                    new_date = episode['date']
                    if new_date < existing_date:
                        all_episodes[title] = episode
            
            logger.info(f"Found {len(episode_dict)} episodes in feed: {feed_url}")
        except Exception as e:
            logger.error(f"Error parsing feed {feed_url}: {str(e)}")
            continue
    
    logger.info(f"Total unique episodes found across all feeds: {len(all_episodes)}")
    return all_episodes

def verify_audio_file(audio_path, expected_url):
    """Verify that an audio file exists."""
    return os.path.exists(audio_path)

def fetch_episodes(episode_dict, audio_dir, tscript_dir):
    """Fetch episodes that don't have transcripts yet."""
    episodes_to_download = []

    for episode in episode_dict:
        title = episode_dict[episode]['title']
        url = episode_dict[episode]['url']
        date = episode_dict[episode]['date']
        filename = episode_dict[episode]['filename']

        # Check if transcript already exists
        transcript_path = os.path.join(tscript_dir, filename)
        if verify_transcript(transcript_path):
            # If transcript exists, we can skip this episode
            continue

        # If we get here, we need this episode
        audio_filename = f"{date}_{title}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        
        # Only download if audio doesn't exist
        if not verify_audio_file(audio_path, url):
            episodes_to_download.append({
                'title': title,
                'url': url,
                'date': date,
                'audio_filename': audio_filename,
                'audio_path': audio_path,
                'filename': filename,
                'path': transcript_path,
            })

    if not episodes_to_download:
        logger.info("No episodes need to be downloaded.")
        return

    logger.info(f"Found {len(episodes_to_download)} episodes to download")
    for episode in episodes_to_download:
        logger.info(f" - {episode['title']}")

    confirmation = input("Do you want to proceed with the download? (yes/no): ")
    if confirmation.lower() != 'yes':
        logger.info("Download aborted.")
        return

    # Download episodes with progress bar
    successful_downloads = []
    failed_downloads = []
    
    for episode in tqdm(episodes_to_download, desc="Downloading episodes"):
        title = episode['title']
        url = episode['url']
        audio_path = episode['audio_path']

        try:
            # Stream download with progress
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Get total file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Open file and write in chunks with progress
            with open(audio_path, 'wb') as f, tqdm(
                desc=f"Downloading {title}",
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                leave=False
            ) as pbar:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    pbar.update(size)
            
            logger.info(f"Successfully downloaded {title}")
            successful_downloads.append(title)
                
        except Exception as e:
            logger.error(f"Error downloading {title}: {str(e)}")
            failed_downloads.append(title)
            # Clean up failed download
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception as e:
                    logger.error(f"Error removing failed download {audio_path}: {str(e)}")
            continue

    # Summary of download results
    logger.info("\nDownload Summary:")
    logger.info(f"Successfully downloaded: {len(successful_downloads)} episodes")
    if failed_downloads:
        logger.info(f"Failed downloads ({len(failed_downloads)} episodes):")
        for title in failed_downloads:
            logger.info(f" - {title}")
        logger.info("You can run the script again to retry failed downloads.")
    
    logger.info("Finished fetching episodes.")

def cleanup_audio_files(audio_path, wav_path=None):
    """Clean up audio files after successful transcription."""
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            logger.info(f"Cleaned up audio file: {audio_path}")
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
            logger.info(f"Cleaned up WAV file: {wav_path}")
    except Exception as e:
        logger.error(f"Error cleaning up audio files: {str(e)}")

# -----------------------------------------------------------------------------
# Transcription functions
# -----------------------------------------------------------------------------
def transcribe_with_server(audio_file, output_path, server_url, model="medium", language="en", output_format="srt", translate=False):
    """Transcribe audio using the remote transcription server."""
    try:
        with open(audio_file, 'rb') as f:
            files = {'file': f}
            data = {
                'model': model,
                'language': language,
                'output-format': output_format,
                'translate': str(translate).lower()
            }
            response = requests.post(f"{server_url}/transcribe", files=files, data=data)
            
            if response.status_code == 200:
                # Parse the JSON response
                try:
                    json_response = response.json()
                    transcript_text = json_response.get('transcript', '')
                    
                    # If we want SRT format but got JSON, convert it
                    if output_format == 'srt' and not transcript_text.strip().startswith('1\n'):
                        # Create a simple SRT format with the entire text as one subtitle
                        srt_content = f"1\n00:00:00,000 --> 00:59:59,999\n{transcript_text}\n\n"
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(srt_content)
                    else:
                        # If we got proper SRT format or want other formats, write as is
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(transcript_text)
                    return True
                except ValueError:
                    # If response is not JSON, write it directly (might be raw SRT)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    return True
            else:
                logger.error(f"Server error: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error during server transcription: {e}")
        return False

def verify_transcript(transcript_path):
    """Verify that a transcript file exists and is not empty."""
    if not os.path.exists(transcript_path):
        return False
    return os.path.getsize(transcript_path) > 0

def transcribe_episodes(wav_dir, tscript_dir, out_format, file_list, audio_dir):
    """Transcribe episodes using either local or server-based transcription."""
    from config import (
        TRANSCRIPT_SERVER_ENABLED,
        TRANSCRIPT_SERVER_URL,
        TRANSCRIPT_MODEL,
        TRANSCRIPT_LANGUAGE,
        TRANSCRIPT_OUTPUT_FORMAT,
        TRANSCRIPT_TRANSLATE
    )
    
    # Build list of files needing transcription
    files_to_transcribe = []
    for audio_file in os.listdir(audio_dir):
        if not audio_file.endswith('.mp3'):
            continue
            
        basename = os.path.splitext(audio_file)[0]
        transcript_path = os.path.join(tscript_dir, f"{basename}.{out_format}")
        
        # Only transcribe if transcript doesn't exist or is empty
        if not verify_transcript(transcript_path):
            audio_path = os.path.join(audio_dir, audio_file)
            files_to_transcribe.append(audio_path)
    
    if not files_to_transcribe:
        logger.info("No episodes need to be transcribed.")
        return
    
    logger.info(f"Found {len(files_to_transcribe)} episodes to transcribe")
    for audio_file in files_to_transcribe:
        logger.info(f" - {os.path.basename(audio_file)}")
    
    confirmation = input("Press Enter to continue with transcription...")
    
    successful_transcripts = []
    failed_transcripts = []
    
    if TRANSCRIPT_SERVER_ENABLED:
        logger.info("Using remote transcription server")
        for audio_file in tqdm(files_to_transcribe, desc="Transcribing"):
            basename = os.path.basename(audio_file)
            name_without_ext = os.path.splitext(basename)[0]
            output_path = os.path.join(tscript_dir, f"{name_without_ext}.{out_format}")
            wav_path = os.path.join(wav_dir, f"{name_without_ext}.wav")
            
            success = transcribe_with_server(
                audio_file,
                output_path,
                TRANSCRIPT_SERVER_URL,
                TRANSCRIPT_MODEL,
                TRANSCRIPT_LANGUAGE,
                TRANSCRIPT_OUTPUT_FORMAT,
                TRANSCRIPT_TRANSLATE
            )
            
            if success and verify_transcript(output_path):
                logger.info(f"Successfully transcribed {basename}")
                successful_transcripts.append(basename)
                # Clean up audio files after successful transcription
                cleanup_audio_files(audio_file, wav_path)
            else:
                logger.error(f"Failed to transcribe {basename}")
                failed_transcripts.append(basename)
                # Remove failed transcript if it exists
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception as e:
                        logger.error(f"Error removing failed transcript {output_path}: {str(e)}")
    else:
        logger.info("Using local transcription")
        # ... existing local transcription code ...
    
    # Summary of transcription results
    logger.info("\nTranscription Summary:")
    logger.info(f"Successfully transcribed: {len(successful_transcripts)} episodes")
    if failed_transcripts:
        logger.info(f"Failed transcriptions ({len(failed_transcripts)} episodes):")
        for basename in failed_transcripts:
            logger.info(f" - {basename}")
        logger.info("You can run the script again to retry failed transcriptions.")

def create_recommendations_prompt(user_interest, db_episodes, semantic_segments):
    """
    Combine metadata from database episodes and semantic search snippets
    into a prompt that requests five recommended episodes from the LLM.
    """
    # Convert db_episodes to text
    db_episode_texts = []
    for ep in db_episodes:
        db_episode_texts.append(
            f"Title: {ep['title']}\nDate: {ep['date']}\nDescription: {ep['description']}\nURL: {ep['url']}\n"
        )

    # Convert semantic_segments to text (if available)
    semantic_texts = []
    if semantic_segments and 'documents' in semantic_segments and semantic_segments['documents'][0]:
        for i, doc in enumerate(semantic_segments['documents'][0]):
            meta = semantic_segments['metadatas'][0][i]
            semantic_texts.append(
                f"Snippet {i+1} from episode {meta['title']}:\n{doc}\n"
            )

    # Build final prompt
    prompt = f"""
You are an expert podcast guide. A user is interested in listening to episodes about: {user_interest}.

Below are possible matches from the database:
{''.join(db_episode_texts)}

Below are transcript snippets from semantic search:
{''.join(semantic_texts)}

Based on the above information, recommend FIVE episodes the user should listen to. 
For each recommended episode, provide:
1. Title
2. Short reason or explanation why it's recommended
3. The URL or reference

Return your response in JSON with the structure:
{{
  "recommendations": [
    {{
      "title": "...",
      "reason": "...",
      "url": "..."
    }},
    ...
  ]
}}
"""
    return prompt

def main():
    print("This is a library of functions supporting turning transcripts into embeddings and storing them to a ChromaDB collection.")
    
if __name__ == "__main__":
    main()

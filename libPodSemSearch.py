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

def fetch_episodes(episode_dict, audio_dir, tscript_dir):
    """Fetch episodes that don't have transcripts yet."""
    episodes_to_download = []

    for episode in episode_dict:
        title = episode_dict[episode]['title']
        url = episode_dict[episode]['url']
        date = episode_dict[episode]['date']
        filename = episode_dict[episode]['filename']

        # Check if the audio file already exists
        audio_filename = f"{date}_{title}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        tscript_path = os.path.join(tscript_dir, filename)

        # Check if transcript file exists
        transcript_files = glob.glob(os.path.join(tscript_dir, f"*{title}*"))
        if not transcript_files:
            logger.info(f"Cannot find episode transcript: {filename}")
            episodes_to_download.append({
                'title': title,
                'url': url,
                'date': date,
                'audio_filename': audio_filename,
                'audio_path': audio_path,
                'filename': filename,
                'path': tscript_path,
            })

    if not episodes_to_download:
        logger.info("No episodes need to be downloaded.")
        return

    logger.info("The following episodes will be downloaded:")
    for episode in episodes_to_download:
        logger.info(f" - {episode['title']}")

    confirmation = input("Do you want to proceed with the download? (yes/no): ")
    if confirmation.lower() != 'yes':
        logger.info("Download aborted.")
        return

    for episode in episodes_to_download:
        title = episode['title']
        url = episode['url']
        audio_path = episode['audio_path']

        logger.info(f"Downloading {title}...")
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Successfully downloaded {title}")
        except Exception as e:
            logger.error(f"Error downloading {title}: {str(e)}")
            continue

    logger.info("Finished fetching episodes.")

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
    
    if TRANSCRIPT_SERVER_ENABLED:
        print("Using remote transcription server")
        for audio_file in tqdm(file_list, desc="Transcribing"):
            basename = os.path.basename(audio_file)
            name_without_ext = os.path.splitext(basename)[0]
            output_path = os.path.join(tscript_dir, f"{name_without_ext}.{out_format}")
            
            success = transcribe_with_server(
                audio_file,
                output_path,
                TRANSCRIPT_SERVER_URL,
                TRANSCRIPT_MODEL,
                TRANSCRIPT_LANGUAGE,
                TRANSCRIPT_OUTPUT_FORMAT,
                TRANSCRIPT_TRANSLATE
            )
            
            if not success:
                print(f"Failed to transcribe {basename}")
                continue
            
            print(f"Successfully transcribed {basename}")
    else:
        print("Using local transcription")
        # ... existing local transcription code ...

def main():
    print("This is a library of functions supporting turning transcripts into embeddings and storing them to a ChromaDB collection.")
    
if __name__ == "__main__":
    main()

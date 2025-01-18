# Script to fetch all episodes of a podcast from the RSS feed
# and save them to a local directory. Each podcast episode is
# saved as a given the same name as its title. All titles, 
# descriptions, and URLs are saved to the postgres database.

import feedparser
import os
import argparse

# Import functions from libPodSemSearch
from libPodSemSearch import (
    gen_filenames,
    add_episodes,
    setup_database,
    fetch_episodes,
    check_dir,
    transcribe_episodes
)

# Import config from config.py
from config import ( 
    feed_url,
    pod_prefix,
    audio_dir,
    tscript_dir,
    audio_dir,
    wav_dir,
    tscript_dir,
)

def parse_args():
    parser = argparse.ArgumentParser(description='Fetch and transcribe podcast episodes')
    parser.add_argument('--server', action='store_true',
                      help='Use remote transcription server instead of local transcription')
    parser.add_argument('--server-url', type=str,
                      help='URL of the transcription server')
    parser.add_argument('--model', type=str, default='medium',
                      help='Transcription model to use (default: medium)')
    parser.add_argument('--language', type=str, default='en',
                      help='Language of the audio (default: en)')
    parser.add_argument('--output-format', type=str, default='srt',
                      help='Output format for transcription (default: srt)')
    parser.add_argument('--translate', action='store_true',
                      help='Enable translation')
    return parser.parse_args()

# Parse command line arguments
args = parse_args()

# Update config with command line arguments if provided
if args.server:
    from config import (
        TRANSCRIPT_SERVER_ENABLED,
        TRANSCRIPT_SERVER_URL,
        TRANSCRIPT_MODEL,
        TRANSCRIPT_LANGUAGE,
        TRANSCRIPT_OUTPUT_FORMAT,
        TRANSCRIPT_TRANSLATE
    )
    import config
    config.TRANSCRIPT_SERVER_ENABLED = True
    if args.server_url:
        config.TRANSCRIPT_SERVER_URL = args.server_url
    if args.model:
        config.TRANSCRIPT_MODEL = args.model
    if args.language:
        config.TRANSCRIPT_LANGUAGE = args.language
    if args.output_format:
        config.TRANSCRIPT_OUTPUT_FORMAT = args.output_format
    config.TRANSCRIPT_TRANSLATE = args.translate

# Check that all directories exist
# First that we have a directory for the podcast
check_dir(pod_prefix, count_files=0, create=1)
# Then the subdirectories
check_dir(audio_dir, count_files=1, create=1)
check_dir(wav_dir, count_files=0, create=1)
check_dir(tscript_dir, count_files=1, create=1)

new_episodes = []    

# First we grab the RSS feed and generate metadata
try:
    rih_feed = feedparser.parse(feed_url)    # Parse RSS feed
except:
    print("Error parsing RSS feed")
    exit()
episode_dict = gen_filenames(rih_feed)    # Generate a dictionary of episode metadata including filenames
print("Successfully obtained episode metadata from RSS feed")

# Setup the database schema if it doesn't exist
print(f'Setting up database schema...')
setup_database()

# Add the new episodes to the database and get a dataframe of all episodes
df_metadata = add_episodes(episode_dict)

# Fetch the episodes and save to audio_dir
# fetch_episodes checks if episodes are already transcribed
fetch_episodes(episode_dict, audio_dir, tscript_dir)

# Transcribe the episodes
file_list = []
for audio_file in os.listdir(audio_dir):
    audio_basename, _ = os.path.splitext(audio_file)
    transcript_exists = any(
        os.path.splitext(srt_file)[0] == audio_basename for srt_file in os.listdir(tscript_dir)
    )
    if not transcript_exists:
        # Print the audio file name and the corresponding transcript file name
        print(f"Transcript for {audio_file} does not exist. Adding to transcription list.")
        # Add the audio file to the list of files to be transcribed
        file_list.append(os.path.join(audio_dir, audio_file))

# Run the transcription if file_list has any contents
if not file_list:
    print("All episodes have been transcribed.")
else:
    # print(f"Files to be transcribed: {file_list}")
    input("Press Enter to continue with transcription...")
    transcribe_episodes(wav_dir, tscript_dir, "srt", file_list, audio_dir)


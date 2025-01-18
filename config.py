# PODCAST
pod_prefix="rihPodcast"
feed_url = 'https://therestishistory.supportingcast.fm/content/eyJ0IjoicCIsImMiOiIxNDc3IiwidSI6Ijc3MTYzNiIsImQiOiIxNjM0OTQwODcyIiwiayI6MjY3fXw2MTViMDljYTBhNTYzNjcxZmI1ZTc0NjJiNmNkMDNmOTA4NjU0NWQ0MWJlOGY3NDgyZGVlNDRjMjVjNjA3ZDZi.rss'

# LLM Settings
max_tokens=240

# DIRECTORIES
tscript_dir=f'{pod_prefix}/transcripts'
audio_dir = f'{pod_prefix}/audio'
wav_dir = f'{pod_prefix}/wav'
tscript_dir = f'{pod_prefix}/transcripts'
index_dir = f'{pod_prefix}/indexdir'

# CHROMA
chromadb_name = f'{pod_prefix}/chroma.db'
chroma_collection = f'{pod_prefix}_{max_tokens}T_Collection'
collection_metadata = {"hnsw:space": "cosine", "model.max_seq_length": max_tokens}

# Transcript server configuration
TRANSCRIPT_SERVER_URL = "http://ragnar.sys.kyomu.co.uk:5000"
TRANSCRIPT_SERVER_ENABLED = True  # Set to True to use server, False for local transcription
TRANSCRIPT_MODEL = "medium"
TRANSCRIPT_LANGUAGE = "en"
TRANSCRIPT_OUTPUT_FORMAT = "srt"
TRANSCRIPT_TRANSLATE = False





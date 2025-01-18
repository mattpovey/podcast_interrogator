# Application settings that don't require environment variables

# UI Configuration
SHOW_PROGRESS = False  # Set to True to enable detailed progress updates

# Podcast Configuration
POD_PREFIX = "your_podcast_name"  # Should match config.py pod_prefix
MAX_TOKENS = 240  # Token limit for text chunks

# Directory Configuration
TSCRIPT_DIR = f'{POD_PREFIX}/transcripts'
AUDIO_DIR = f'{POD_PREFIX}/audio'
WAV_DIR = f'{POD_PREFIX}/wav'
INDEX_DIR = f'{POD_PREFIX}/indexdir'

# ChromaDB Configuration
CHROMADB_NAME = f'{POD_PREFIX}/chroma.db'
CHROMA_COLLECTION = f'{POD_PREFIX}_{MAX_TOKENS}T_Collection'
COLLECTION_METADATA = {
    "hnsw:space": "cosine",
    "model.max_seq_length": MAX_TOKENS
}

# Transcript Server Configuration
TRANSCRIPT_SERVER_ENABLED = False  # Set to True to use server, False for local transcription
TRANSCRIPT_MODEL = "medium"  # Whisper model size: tiny, base, small, medium, large
TRANSCRIPT_LANGUAGE = "en"  # Language code for transcription
TRANSCRIPT_OUTPUT_FORMAT = "srt"  # Output format for transcripts
TRANSCRIPT_TRANSLATE = False  # Whether to translate non-English content

# LLM Configuration
LLM_PROVIDER = 'OpenAI'  # Provider name for display
LLM_API_KEY = None  # Set via environment variable
LLM_API_BASE = 'https://api.openai.com/v1'  # Base URL for API
LLM_MODEL = None  # Set via environment variable
LLM_TEMPERATURE = 0.1  # Default temperature for completions
LLM_TOP_P = 0.1  # Default top_p for completions

# Search Configuration
ELASTICSEARCH_INDEX = f'{POD_PREFIX.lower()}'  # Lowercase for ES compatibility
SEMANTIC_COLLECTION = f'{POD_PREFIX.lower()}_semantic'
POSTGRES_DB = POD_PREFIX.lower()
DOCKER_PREFIX = 'podcast-search'  # Base prefix for Docker resources 
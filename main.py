import os 
import re
import sys
import shutil
import time
import logging
from logging.handlers import RotatingFileHandler
import google.genai as genai
from utils import has_frontmatter, build_latch_frontmatter, extract_frontmatter, merge_frontmatter, classify_note

# Get path from environment variable (default is /app/vault for Docker compatibility)
VAULT_PATH = os.getenv("VAULT_PATH", "/app/vault")
SOURCE_DIR = os.path.join(VAULT_PATH, "00_Inbox")

# Setup logging
logger = logging.getLogger("OAC")
logger.setLevel(logging.DEBUG)

# Ensure logs directory exists
LOGS_DIR = "/app/logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Create formatter
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create RotatingFileHandler
log_file = os.path.join(LOGS_DIR, "app.log")
handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Check if directory exists before running
if not os.path.exists(SOURCE_DIR):
    logger.error(f"Directory {SOURCE_DIR} does not exist. Please check the mount point.")
    sys.exit(1)

# Check API key
gemini_key = os.environ.get("GEMINI_API_KEY")
if not gemini_key:
    logger.error("Please set the GEMINI_API_KEY environment variable before running.")
    sys.exit(1)

# Configure genai API
client = genai.Client(api_key=gemini_key)

# Model configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
logger.info(f"Using Gemini model: {GEMINI_MODEL}")

# Rate limiting: 2 requests/second = 0.5 seconds per request
MIN_REQUEST_INTERVAL = 0.5
last_request_time_holder = {'value': 0.0}

# Retry configuration for API failures
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Define IPARAG structure
STRUCTURE = {
    "00_Inbox": "Capture point. Everything unprocessed lands here. Process to zero regularly.",
    "10_Projects": "Projects with deadlines and specific goals.",
    "20_Areas": "Ongoing responsibilities with no end date. Life domains you maintain.",
    "30_Resources": "Reference material, templates, guides, SOPs",
    "40_Archives": "Completed projects and past content.",
    "50_Galaxy": "Zettelkasten — permanent notes, one concept per note, flat file structure"
}

NORMALIZED_KEYS = {k.lower(): k for k in STRUCTURE.keys()}

# Ensure IPARAG folders exist
for folder in STRUCTURE.keys():
    folder_path = os.path.join(VAULT_PATH, folder)
    os.makedirs(folder_path, exist_ok=True)


if __name__ == "__main__":
    moved = 0
    skipped = 0

    logger.info("=== OAC Started ===")

    # Read GEMINI.md if available
    gemini_md_path = os.path.join(VAULT_PATH, "GEMINI.md")
    gemini_context = None
    if os.path.exists(gemini_md_path):
        try:
            with open(gemini_md_path, 'r', encoding='utf-8') as f:
                gemini_context = f.read()
            logger.info("Loaded custom instructions from GEMINI.md")
        except Exception as e:
            logger.warning(f"Failed to read GEMINI.md: {e}")

    # Count total markdown files
    all_files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(".md") and os.path.isfile(os.path.join(SOURCE_DIR, f))]
    total_files = len(all_files)
    logger.info(f"Found {total_files} markdown file(s) to process in {SOURCE_DIR}")
    
    if total_files == 0:
        logger.info("No files to process. Exiting.")
        sys.exit(0)

    for index, filename in enumerate(all_files, 1):
        file_path = os.path.join(SOURCE_DIR, filename)
        logger.info(f"[{index}/{total_files}] Processing: {filename}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not has_frontmatter(content):
            logger.debug(f"  Creating frontmatter...")
            new_frontmatter = build_latch_frontmatter(file_path, None, SOURCE_DIR)
            content = f"{new_frontmatter}{content}"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        logger.debug(f"  Classifying note...")
        target_folder = classify_note(content, client, STRUCTURE, NORMALIZED_KEYS, MAX_RETRIES, 
                                      RETRY_DELAY, MIN_REQUEST_INTERVAL, GEMINI_MODEL, logger, 
                                      gemini_context, last_request_time_holder)
        if not target_folder:
            # Could not classify, but still update frontmatter
            logger.warning(f"  Unable to determine folder, keeping in 00_Inbox")
            # Update frontmatter intelligently: merge if exists, create if not
            existing_fm, body = extract_frontmatter(content)
            if existing_fm:
                new_content = merge_frontmatter(existing_fm, file_path, "00_Inbox", SOURCE_DIR) + body
            else:
                new_content = build_latch_frontmatter(file_path, "00_Inbox", SOURCE_DIR) + body
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            skipped += 1
            continue

        # Update frontmatter intelligently: merge if exists, create if not
        existing_fm, body = extract_frontmatter(content)
        if existing_fm:
            content = merge_frontmatter(existing_fm, file_path, target_folder, SOURCE_DIR) + body
        else:
            content = build_latch_frontmatter(file_path, target_folder, SOURCE_DIR) + body
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        dest_dir = os.path.join(VAULT_PATH, target_folder)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)

        logger.info(f"  Moving {filename} -> {target_folder}")
        shutil.move(file_path, dest_path)
        moved += 1

    logger.info("===== COMPLETED =====")
    logger.info(f"Total files processed: {total_files}")
    logger.info(f"Successfully moved: {moved}")
    logger.info(f"Skipped (no classification): {skipped}")
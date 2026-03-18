import os
import datetime
import re
import time
import google.genai as genai


def has_frontmatter(content):
    stripped = content.lstrip()
    if not stripped.startswith('---'):
        return False
    parts = stripped.split('---', 2)
    return len(parts) >= 3 and parts[1].strip() != ''


def extract_frontmatter(content):
    """
    Extract frontmatter from markdown content.
    
    Returns:
        Tuple of (frontmatter_string, body_content)
    """
    stripped = content.lstrip()
    if not stripped.startswith('---'):
        return None, content
    
    parts = stripped.split('---', 2)
    if len(parts) < 3:
        return None, content
    
    frontmatter_str = parts[1].strip()
    body = parts[2] if len(parts) > 2 else ""
    
    return frontmatter_str, body


def parse_frontmatter_yaml(frontmatter_str):
    """
    Simple YAML parser for frontmatter.
    
    Returns:
        Dictionary of key-value pairs
    """
    if not frontmatter_str:
        return {}
    
    data = {}
    for line in frontmatter_str.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            data[key] = value
    
    return data


def merge_frontmatter(existing_frontmatter_str, file_path, target_folder, source_dir=None):
    """
    Merge existing frontmatter with new properties from build_latch_frontmatter.
    Only adds missing properties without duplicating existing ones.
    
    Args:
        existing_frontmatter_str: Existing frontmatter content (between --- delimiters)
        file_path: Path to the markdown file
        target_folder: Target IPARAG folder
        source_dir: Original source directory
    
    Returns:
        Formatted merged YAML frontmatter string
    """
    # Parse existing frontmatter
    existing = parse_frontmatter_yaml(existing_frontmatter_str)
    
    # Generate new frontmatter structure
    base = os.path.basename(file_path)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
    created_date = mtime.strftime("%Y-%m-%d")
    
    location = target_folder if target_folder else "00_Inbox"
    note_type = target_folder.split('_')[1] if target_folder and '_' in target_folder else "Unclassified"
    
    # Define new properties to add
    new_properties = {
        'tags': '[tag/here]',
        'created': created_date,
        'type': note_type,
        'location': location,
        'up': ''
    }
    
    # Merge: keep existing, add missing
    merged = existing.copy()
    for key, value in new_properties.items():
        if key not in merged:
            merged[key] = value
    
    # Format back to YAML
    result = "---\n"
    for key, value in merged.items():
        result += f"{key}: {value}\n"
    result += "---\n\n"
    
    return result


def build_latch_frontmatter(file_path, target_folder, source_dir=None):
    """
    Build LATCH-format frontmatter for a note.
    
    Args:
        file_path: Path to the markdown file
        target_folder: Target IPARAG folder (e.g., '10_Projects', '20_Areas')
        source_dir: Original source directory (for fallback)
    
    Returns:
        Formatted YAML frontmatter string
    """
    base = os.path.basename(file_path)
    title = os.path.splitext(base)[0]
    
    # Get created date in YYYY-MM-DD format
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
    created_date = mtime.strftime("%Y-%m-%d")
    
    # Determine location and type from target_folder
    location = target_folder if target_folder else "00_Inbox"
    note_type = target_folder.split('_')[1] if target_folder and '_' in target_folder else "Unclassified"
    
    # Format frontmatter with template
    return f"""---
tags: [tag/here]
created: {created_date}
type: {note_type}
location: {location}
up: 
---\n\n"""


def classify_note(content, client, structure, normalized_keys, max_retries, retry_delay, 
                  min_request_interval, gemini_model, logger, gemini_context=None, last_request_time_holder=None):
    """
    Classify a note and determine its target folder.
    
    Args:
        content: Note content to classify
        client: Gemini API client
        structure: IPARAG structure dictionary
        normalized_keys: Normalized folder keys mapping
        max_retries: Maximum number of API retry attempts
        retry_delay: Delay between retries in seconds
        min_request_interval: Minimum interval between API requests
        gemini_model: Model name to use for classification
        logger: Logger instance
        gemini_context: Optional custom context/instructions
        last_request_time_holder: Optional dict to hold last request time {'value': 0.0}
    
    Returns:
        Target folder name or None if classification failed
    """
    if last_request_time_holder is None:
        last_request_time_holder = {'value': 0.0}
    
    # Build simplified prompt to minimize token usage
    folder_list = ", ".join(structure.keys())
    
    context_section = ""
    if gemini_context:
        context_section = f"\n{gemini_context}\n"
    
    prompt = f"""Choose the best folder for this note: {folder_list}
{context_section}
Note: {content[:500]}

Respond with ONLY the folder name, nothing else."""
    
    # Retry logic for API calls
    for attempt in range(1, max_retries + 1):
        try:
            # Rate limiting: ensure at least min_request_interval seconds between requests
            elapsed = time.time() - last_request_time_holder['value']
            if elapsed < min_request_interval:
                time.sleep(min_request_interval - elapsed)
            
            logger.debug(f"  API call attempt {attempt}/{max_retries}")
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config={"max_output_tokens": 256}
            )
            last_request_time_holder['value'] = time.time()
            
            # Validate response
            if not response:
                raise ValueError("Empty response from API")
            
            # Check if response has content
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = str(candidate.finish_reason)
                    if 'MAX_TOKENS' in finish_reason:
                        raise ValueError(f"Response truncated (MAX_TOKENS reached)")
                
                # Try to get text from content
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text')]
                    if text_parts:
                        text = text_parts[0]
                    else:
                        raise ValueError("No text content in response parts")
                else:
                    raise ValueError("No content parts in response")
            else:
                raise ValueError("No candidates in response")
            
            text = text.strip().splitlines()[0]

            # Remove extra punctuation and whitespace
            text = re.sub(r"[^\w\- _]", "", text).strip()

            if text in structure:
                logger.debug(f"  Classification successful: {text}")
                return text
            if text.lower() in normalized_keys:
                logger.debug(f"  Classification successful (normalized): {text}")
                return normalized_keys[text.lower()]

            logger.warning(f"Invalid classification result: '{text}'")
            return None
            
        except Exception as exc:
            error_str = str(exc)
            
            # Check if error is retryable (transient)
            is_retryable = any(keyword in error_str.lower() for keyword in [
                'timeout', 'connection', 'refused', 'unreachable', 
                'temporarily', 'unavailable', 'rate limit', '503', '504'
            ])
            
            if attempt < max_retries and is_retryable:
                wait_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(f"  Attempt {attempt}/{max_retries} failed: {exc}")
                logger.warning(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                # Not retryable or final attempt
                if attempt == max_retries:
                    logger.error(f"Failed after {max_retries} attempts: {exc}")
                else:
                    logger.error(f"Permanent error: {exc}")
                return None

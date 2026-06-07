# Structured Logging System

Centralized logging configuration for the entire funding MVP pipeline.

## Architecture

### Core Module: `logger.py`

Provides `get_logger(module_name)` function that returns a configured logger with:
- **Console output**: INFO level (important events)
- **File output**: DEBUG level (detailed events) → `logs/app.log`

## Log Format

```
YYYY-MM-DD HH:MM:SS | LEVEL    | MODULE          | MESSAGE
2026-06-07 16:31:51 | INFO     | profiler        | Cache hit for ging_github_io (expires 2026-07-07T16:15:53)
2026-06-07 16:31:51 | DEBUG    | matcher         | Sector multipliers applied - primary: 2, secondary: 0, none: 0
```

## Logging by Module

### `fetcher.py`
```
Fetched <url> - <chars> chars, HTTP <status>, fallback=<bool>
Could not fetch <url> - all candidates failed
```
- URL fetches with text length and HTTP status
- Fallback mechanism tracking (HTTPS → HTTP)

### `profiler.py`
```
Cache hit for <filename> (expires <date>)
Cache miss for <filename> (file not found)
Cache expired for <filename> (expired <date>)
Claude API call finished - <tokens> tokens (~$<cost>)
Sector classified as <sector> for <url>
Profile parsed successfully for <url>
```
- Cache hit/miss with expiration tracking
- Claude API calls with token count and cost estimate
- Sector classification results
- Profile parsing status

### `matcher.py`
```
Loaded 50 calls from calls.txt
Filtered out 6 closed calls, 44 open/upcoming calls
Sector multipliers applied - primary: 25, secondary: 15, none: 4
Top score: 0.3900 (HORIZON-JU-CBE-2026-IA-04)
```
- Total calls loaded from source file
- Closed vs. open/upcoming call count
- Sector multiplier statistics (how many calls got each boost)
- Best matching opportunity score

### `sector_mapping.py`
```
Sector classification - primary: DIGITAL_TECH, secondary: ['EDUCATION_LEARNING', 'SECURITY_DEFENCE']
Primary sector score: {'required_matches': 6, 'optional_matches': 9, 'total_score': 21}
```
- Primary and secondary sector classification
- Match statistics per sector

### `api.py`
```
Analyze request received: https://ging.github.io/ (force_refresh=False)
Analyze request completed - 5 opportunities found in 2.34s
Profiling failed for <url>: <error>
Matching failed for <url>: <error>
```
- API request details (URL, refresh flag)
- Total processing time
- Error handling with context

### `main.py`
```
Starting profiling for: https://ging.github.io/
Found 2 matching opportunities
```
- High-level orchestration tracking

## Log Levels

### INFO (Console + File)
Essential operational events:
- Successful operations (cache hits, API calls completed)
- Important transitions (profile parsed, calls filtered)
- Results and statistics

### DEBUG (File only)
Detailed diagnostic information:
- Cache misses and expirations
- Intermediate steps (returning cached profile)
- Detailed multiplier statistics

### WARNING (Console + File)
Exceptional conditions:
- Could not fetch URL
- Fetch errors
- Missing data

### ERROR (Console + File)
Failure conditions:
- Profile parsing errors
- API failures
- Matching errors

## Usage in Code

```python
from logger import get_logger

logger = get_logger("module_name")

logger.info("Important operation completed")
logger.debug("Detailed diagnostic info")
logger.warning("Unexpected but handled condition")
logger.error("Operation failed")
```

## Output Destinations

### Console (Logger Level: INFO)
```
2026-06-07 16:31:51 | INFO     | profiler        | Cache hit for ging_github_io
2026-06-07 16:31:51 | INFO     | matcher         | Loaded 8 calls from calls.txt
```

### File: `logs/app.log` (Logger Level: DEBUG)
```
2026-06-07 16:31:51 | DEBUG    | fetcher         | Fetching URL: https://ging.github.io/
2026-06-07 16:31:51 | INFO     | profiler        | Cache hit for ging_github_io
2026-06-07 16:31:51 | DEBUG    | matcher         | Sector multipliers applied - primary: 2, secondary: 0, none: 0
```

## File Management

Log file: `logs/app.log`
- Append-only (logs accumulate)
- UTF-8 encoding
- Created automatically if missing
- Size management: User should rotate/clear periodically

## Benefits

✅ **Debugging**: Full event trail in `logs/app.log`  
✅ **Monitoring**: Console shows important events without noise  
✅ **Transparency**: Clear visibility into what the system is doing  
✅ **Performance**: Track API calls, cache hits, processing times  
✅ **Error tracking**: Full context when things fail  
✅ **Unified format**: Consistent timestamp | level | module | message

## Example Output

```
2026-06-07 16:31:51 | INFO     | main            | Starting profiling for: https://ging.github.io/
2026-06-07 16:31:51 | INFO     | profiler        | Analyzing group: https://ging.github.io/ (force_refresh=False)
2026-06-07 16:31:51 | INFO     | profiler        | Cache hit for ging_github_io (expires 2026-07-07T16:15:53)
2026-06-07 16:31:51 | DEBUG    | profiler        | Returning cached profile for https://ging.github.io/
2026-06-07 16:31:51 | INFO     | matcher         | Loaded 8 calls from calls.txt
2026-06-07 16:31:51 | INFO     | matcher         | Filtered out 6 closed calls, 2 open/upcoming calls
2026-06-07 16:31:51 | DEBUG    | matcher         | Sector multipliers applied - primary: 2, secondary: 0, none: 0
2026-06-07 16:31:51 | INFO     | matcher         | Top score: 0.1333 (HORIZON-CL5-2026-10-D6-03)
2026-06-07 16:31:51 | INFO     | main            | Found 2 matching opportunities
```

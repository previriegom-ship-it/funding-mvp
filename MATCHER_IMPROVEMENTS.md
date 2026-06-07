# Matcher Improvements: Sector-Based Call Scoring

Enhanced `matcher.py` to boost relevant funding calls based on research group sector alignment.

## Implementation

### New Functions

#### `get_call_sector(call: dict) -> str`
Classifies each funding call into a sector based on its TÍTULO and SCOPE.
- Uses keywords from sector_mapping.py
- Returns sector code (e.g., "DIGITAL_TECH") or "UNKNOWN"
- Exact same logic as profile sector classification for consistency

#### `score_call(profile_weights, call, profile=None) -> tuple[float, str]`
Enhanced scoring function that applies sector multipliers.

Returns: `(final_score, sector_match)`
- **final_score**: Base keyword score × sector multiplier
- **sector_match**: "primary" | "secondary" | "none"

**Sector Multipliers:**
- Primary sector match: ×1.2 (boost relevant calls)
- Secondary sector match: ×1.0 (no change)
- No sector match: ×0.7 (penalize irrelevant calls)

#### Updated `match()` function
Now includes `sector_match` field in results for transparency.

## Example Impact: GING (DIGITAL_TECH)

### Before Sector Matching
```
Base Score: 0.0688 (DIGITAL_TECH call)
Base Score: 0.1089 (Unknown sector call)
```

### After Sector Matching
```
Final Score: 0.1180 (DIGITAL_TECH call)     → 1.72x boost
Final Score: 0.1089 (Unknown sector call)   → no change
Sector Match: "primary" | "none"
```

### Result
Digital technology calls rank significantly higher, matching GING's research focus.

## Output Fields

Calls are returned with enhanced metadata:

```python
{
    "id": "HORIZON-CL4-2027-04-DIGITAL-EMERGING-10",
    "title": "Horizon scanning and foresight in future digital technologies",
    "status": "Próximamente",
    "score": 0.1180,           # final score with multiplier
    "sector_match": "primary",  # primary/secondary/none
    "deadline": "2027-06-15"
}
```

## Behavior

### DIGITAL_TECH Group (GING)
- AI/ML/Data calls: 1.2x boost (primary match)
- Internet/Network calls: 1.2x boost
- Robotics calls: 1.0x (secondary match)
- Bio/Health calls: 0.7x (no match)

### HEALTH_BIOMEDICAL Group
- Medical/Drug discovery calls: 1.2x boost
- Digital health calls: 1.0x (secondary match)
- Pure digital calls: 0.7x (no match)

## Algorithm

1. Normalize call text (TÍTULO + SCOPE)
2. Classify call to sector using keyword matching
3. Calculate base score (keyword overlap with profile)
4. Apply multiplier based on sector alignment:
   - If call_sector == profile.primary_sector → ×1.2
   - If call_sector in profile.secondary_sectors → ×1.0
   - Otherwise → ×0.7
5. Return final score and sector match type

## Testing

Run `test_sector_matching.py` to see:
- GING profile (DIGITAL_TECH) with top 10 calls
- Manual biomedical profile with top 10 calls
- Sector match indicators for each result

Run `test_sector_impact.py` to see:
- Before/after scores for sample calls
- Multiplier effects by sector alignment

## Integration

Sector matching is automatically applied when:
1. Profile contains sector information (from `profiler.py`)
2. `match()` is called with that profile
3. Calls are scored with sector consideration

Backward compatible: Works with profiles without sector information (multiplier=1.0).

## Future Enhancements

- Confidence scores per sector classification
- Sub-sector matching (e.g., DIGITAL_TECH → "AI" vs "Networks")
- Keyword highlight in results (which keywords matched)
- Sector trend analysis (rising/falling sectors in open calls)

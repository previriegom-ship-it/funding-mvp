# Sector Classification System

Automatic classification of research group profiles into 10 funding sectors.

## Implementation

### New Files Created
- **sector_mapping.py**: Core classification engine with 10 sectors and their keywords

### Modified Files  
- **profiler.py**: Updated `analyze_group()` to call `classify_sectors()` and add sector fields to profile JSON

### Functions

#### `classify_sectors(profile: dict) -> dict`

Classifies a research profile into primary and secondary sectors.

Returns:
```json
{
  "primary_sector": "DIGITAL_TECH",
  "primary_sector_label": "Digital Technologies",
  "primary_sector_score": {
    "required_matches": 4,
    "optional_matches": 10,
    "total_score": 18
  },
  "secondary_sectors": [
    {
      "sector": "EDUCATION_LEARNING",
      "label": "Education & Learning",
      "score": {
        "required_matches": 4,
        "optional_matches": 0,
        "total_score": 8
      }
    }
  ]
}
```

## 10 Sectors

1. **DIGITAL_TECH** - Digital Technologies
   - AI, machine learning, deep learning, computer vision, data science, internet, networks, protocols

2. **HEALTH_BIOMEDICAL** - Health & Biomedical
   - Biomedical, clinical, disease, medical imaging, genomics, therapy, diagnosis

3. **MOBILITY_TRANSPORT** - Mobility & Transport
   - Autonomous vehicles, connected vehicles, road safety, traffic management, fleet management

4. **ENERGY_CLIMATE** - Energy & Climate
   - Renewable energy, solar, wind, battery, grid, climate change, decarbonization

5. **ROBOTICS_AUTOMATION** - Robotics & Automation
   - Robots, automation, control systems, SLAM, human-robot interaction, drones

6. **MANUFACTURING_INDUSTRY** - Manufacturing & Industry 4.0
   - Manufacturing, production, quality control, 3D printing, smart factory, Industry 4.0

7. **SECURITY_DEFENCE** - Security & Defence
   - Cybersecurity, cryptography, privacy, threat detection, network security

8. **EDUCATION_LEARNING** - Education & Learning
   - Education, e-learning, teaching, curriculum, learning analytics, adaptive learning

9. **AGRICULTURE_FOOD** - Agriculture & Food
   - Agriculture, food, farming, crop, irrigation, precision agriculture, food security

10. **MATERIALS_ADVANCED** - Advanced Materials
    - Materials, nanotechnology, composites, polymers, ceramics, tissue engineering

## Classification Algorithm

1. Extracts all text from profile fields (name, keywords, description, research lines, etc.)
2. Normalizes text (lowercase, abbreviation expansion like "AI" → "artificial intelligence")
3. Counts keyword matches for each sector:
   - Required keywords: weighted 2x more heavily
   - Optional keywords: weighted 1x
4. Ranks sectors by total score
5. Returns primary sector and secondary sectors with scores

## Example: GING

**Input**: Next Generation Internet Group profile

**Classification**:
- Primary: **DIGITAL_TECH** (18 points: 4 required + 10 optional)
- Secondary: EDUCATION_LEARNING (8 points), SECURITY_DEFENCE (4 points)

This correctly identifies GING as a digital technologies group with secondary focus on education.

## Integration with Cache System

Sector classification fields are automatically added to cached profiles:
```
profiles/cache/ging_github_io.json
  - primary_sector
  - primary_sector_label
  - primary_sector_score
  - secondary_sectors
```

## Future Improvements

- Add confidence scores per sector
- Implement sector exclusivity rules (if A is primary, reduce B's weight)
- Add sub-sectors within each main sector
- Interactive sector refinement API

"""Automatic sector classification for research group profiles.

Maps research profiles to 10 funding sectors based on required and optional keywords.
"""

import re
from logger import get_logger

logger = get_logger("sector_mapping")

# Sector definitions with required and optional keywords
SECTORS = {
    "DIGITAL_TECH": {
        "label": "Digital Technologies",
        "required": [
            "artificial intelligence", "machine learning", "deep learning", "neural network",
            "natural language processing", "computer vision", "data science", "big data",
            "knowledge graph", "semantic web", "ontology", "federated learning",
            "internet", "network", "protocol", "software"
        ],
        "optional": [
            "graph neural network", "transformer", "llm", "reinforcement learning",
            "recommendation system", "explainable ai", "edge computing", "cloud computing",
            "distributed systems", "internet of things", "iot", "digital twin",
            "network analysis", "speech recognition", "generative ai", "rag",
            "vector database", "web", "data processing", "platform", "system",
            "multimedia", "videoconferencing", "communication"
        ]
    },
    "HEALTH_BIOMEDICAL": {
        "label": "Health & Biomedical",
        "required": [
            "health", "biomedical", "clinical", "patient", "disease",
            "medical imaging", "drug discovery", "genomics", "bioinformatics",
            "diagnosis", "therapy", "public health", "epidemiology", "mental health"
        ],
        "optional": [
            "proteomics", "metabolomics", "electronic health record", "ehr",
            "personalized medicine", "precision medicine", "wearable health",
            "brain-computer interface", "rehabilitation", "cancer", "oncology",
            "cardiovascular", "neurology", "rare disease", "medical device",
            "digital health", "telemedicine"
        ]
    },
    "MOBILITY_TRANSPORT": {
        "label": "Mobility & Transport",
        "required": [
            "autonomous vehicle", "connected vehicle", "road safety", "traffic",
            "transport", "mobility", "vehicle", "highway", "infrastructure",
            "accident", "crash", "driver behavior", "fleet management"
        ],
        "optional": [
            "ccam", "cooperative mobility", "smart city", "urban mobility",
            "electric vehicle", "ev", "charging", "emission", "co2 transport",
            "logistics", "supply chain", "railway", "aviation", "maritime",
            "adas", "perception system", "lidar", "radar", "v2x", "platooning",
            "pedestrian", "cyclist", "vulnerable road user", "speed",
            "driving simulation", "test track"
        ]
    },
    "ENERGY_CLIMATE": {
        "label": "Energy & Climate",
        "required": [
            "energy", "renewable", "solar", "wind", "battery", "grid", "power",
            "climate change", "carbon", "emission reduction", "sustainability",
            "decarbonization", "photovoltaic", "hydrogen"
        ],
        "optional": [
            "smart grid", "microgrid", "energy storage", "fuel cell",
            "building energy", "energy efficiency", "hvac", "demand response",
            "carbon capture", "net zero", "green deal", "energy poverty",
            "district heating", "biomass", "geothermal", "tidal",
            "energy community", "prosumer", "peer-to-peer energy",
            "carbon footprint", "life cycle assessment"
        ]
    },
    "ROBOTICS_AUTOMATION": {
        "label": "Robotics & Automation",
        "required": [
            "robot", "robotics", "autonomous system", "control system", "automation",
            "actuator", "sensor fusion", "manipulation", "path planning",
            "slam", "human-robot interaction"
        ],
        "optional": [
            "collaborative robot", "cobot", "exoskeleton", "drone", "uav",
            "underwater robot", "space robotics", "surgical robot",
            "industrial robot", "mobile robot", "legged robot", "motion planning",
            "kinematics", "dynamics", "ros", "computer vision robotics",
            "grasping", "teleoperation", "swarm robotics", "multi-robot"
        ]
    },
    "MANUFACTURING_INDUSTRY": {
        "label": "Manufacturing & Industry 4.0",
        "required": [
            "manufacturing", "production", "industrial process", "factory",
            "quality control", "supply chain", "additive manufacturing",
            "3d printing", "cnc", "industry 4.0", "smart factory"
        ],
        "optional": [
            "digital twin manufacturing", "predictive maintenance",
            "condition monitoring", "asset management", "mes", "erp",
            "lean manufacturing", "six sigma", "process optimization",
            "welding", "casting", "machining", "composite material",
            "aerospace manufacturing", "automotive manufacturing",
            "circular economy", "remanufacturing"
        ]
    },
    "SECURITY_DEFENCE": {
        "label": "Security & Defence",
        "required": [
            "cybersecurity", "security", "cryptography", "privacy",
            "threat detection", "intrusion detection", "vulnerability",
            "authentication", "encryption", "network security", "firewall"
        ],
        "optional": [
            "zero trust", "siem", "soc", "malware", "ransomware",
            "blockchain security", "iot security", "cloud security",
            "critical infrastructure", "scada security", "ot security",
            "data protection", "gdpr", "identity management",
            "quantum cryptography", "post-quantum"
        ]
    },
    "EDUCATION_LEARNING": {
        "label": "Education & Learning",
        "required": [
            "education", "learning", "teaching", "pedagogy", "curriculum",
            "e-learning", "educational technology", "edtech", "student",
            "adaptive learning", "learning analytics"
        ],
        "optional": [
            "moocs", "gamification", "serious game", "virtual classroom",
            "competency-based", "personalized learning", "tutoring system",
            "higher education", "vocational training", "stem education",
            "assessment", "feedback", "augmented reality education",
            "vr education"
        ]
    },
    "AGRICULTURE_FOOD": {
        "label": "Agriculture & Food",
        "required": [
            "agriculture", "food", "crop", "farming", "soil", "irrigation",
            "livestock", "aquaculture", "bioeconomy", "food security",
            "agri-tech", "precision agriculture", "plant"
        ],
        "optional": [
            "smart farming", "drone agriculture", "satellite agriculture",
            "pesticide", "fertilizer", "organic farming", "vertical farming",
            "food processing", "food safety", "traceability food",
            "circular bioeconomy", "biowaste", "composting",
            "forest management", "biodiversity", "water management agriculture"
        ]
    },
    "MATERIALS_ADVANCED": {
        "label": "Advanced Materials",
        "required": [
            "material", "nanotechnology", "nanoparticle", "composite",
            "polymer", "ceramic", "alloy", "coating", "thin film",
            "surface engineering", "material characterization"
        ],
        "optional": [
            "graphene", "carbon nanotube", "metamaterial", "smart material",
            "biomaterial", "scaffold", "tissue engineering", "semiconductor",
            "photonic material", "magnetic material", "corrosion", "fatigue",
            "material simulation", "dft", "molecular dynamics",
            "sustainable material", "bio-based material"
        ]
    }
}


def _normalize_text(text: str) -> str:
    """Normalize text for keyword matching (lowercase, basic cleanup)."""
    text = text.lower()
    # Replace common abbreviations with their full forms for better matching
    text = text.replace("ai ", "artificial intelligence ")
    text = text.replace(" ai ", " artificial intelligence ")
    text = text.replace("llms", "large language models")
    text = text.replace("llm", "large language model")
    text = text.replace("iot", "internet of things")
    text = text.replace("uav", "unmanned aerial vehicle")
    text = text.replace("adas", "advanced driver assistance system")
    text = text.replace("ev ", "electric vehicle ")
    text = text.replace("ehr", "electronic health record")
    text = text.replace("slam", "simultaneous localization and mapping")
    text = text.replace("cnc", "computer numerical control")
    return text


def _score_sector(text: str, sector: dict) -> tuple[int, int]:
    """Score a sector: (required_matches, optional_matches).

    Uses substring matching with some normalization for flexibility.
    """
    normalized = _normalize_text(text)

    # Count required keyword matches
    required = 0
    for kw in sector["required"]:
        # Match as whole phrase or word (at word boundaries where reasonable)
        if kw in normalized:
            required += 1

    # Count optional keyword matches
    optional = 0
    for kw in sector["optional"]:
        if kw in normalized:
            optional += 1

    return required, optional


def classify_sectors(profile: dict) -> dict:
    """Classify research profile into primary and secondary sectors.

    Args:
        profile: Research group profile dict

    Returns:
        Dict with keys:
            primary_sector: str (sector code)
            primary_sector_label: str (human-readable name)
            primary_sector_score: dict (required and optional keyword matches)
            secondary_sectors: list of dicts with sector, label, score

    Returns empty classification if profile has errors.
    """
    if "error" in profile:
        return {
            "primary_sector": None,
            "primary_sector_label": None,
            "primary_sector_score": {},
            "secondary_sectors": []
        }

    # Extract all text from profile
    text_parts = []
    for field in ["name", "explanation", "primary_keywords", "secondary_keywords",
                  "interdisciplinary_topics", "technologies_developed",
                  "technical_capabilities", "application_domains",
                  "research_lines"]:
        value = profile.get(field)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    # For research lines, extract name, description, keywords
                    text_parts.append(str(item.get("name", "")))
                    text_parts.append(str(item.get("description", "")))
                    text_parts.extend(str(k) for k in item.get("keywords", []))
                else:
                    text_parts.append(str(item))
        elif value:
            text_parts.append(str(value))

    full_text = " ".join(text_parts)

    # Score all sectors
    scores = {}
    for sector_code, sector_def in SECTORS.items():
        req, opt = _score_sector(full_text, sector_def)
        scores[sector_code] = {
            "required_matches": req,
            "optional_matches": opt,
            "total_score": req * 2 + opt  # Weight required keywords more heavily
        }

    # Rank sectors
    ranked = sorted(
        scores.items(),
        key=lambda x: (x[1]["total_score"], x[1]["required_matches"]),
        reverse=True
    )

    if not ranked or ranked[0][1]["total_score"] == 0:
        return {
            "primary_sector": None,
            "primary_sector_label": None,
            "primary_sector_score": {},
            "secondary_sectors": []
        }

    # Primary sector
    primary_code, primary_score = ranked[0]
    primary_def = SECTORS[primary_code]

    # Secondary sectors (with scores > 0)
    secondary = []
    for sector_code, score in ranked[1:]:
        if score["total_score"] == 0:
            break
        secondary.append({
            "sector": sector_code,
            "label": SECTORS[sector_code]["label"],
            "score": score
        })

    secondary_codes = [s["sector"] for s in secondary]
    logger.info(f"Sector classification - primary: {primary_code}, secondary: {secondary_codes}")
    logger.debug(f"Primary sector score: {primary_score}")

    return {
        "primary_sector": primary_code,
        "primary_sector_label": primary_def["label"],
        "primary_sector_score": primary_score,
        "secondary_sectors": secondary
    }

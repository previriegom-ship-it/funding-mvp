"""Extract structured data from Horizon Europe call scope text.

Given a call dict (with ID, SCOPE, BUDGET, ACTION, DEADLINE fields), extracts:
- Work packages (WP1, WP2, …)
- Deliverables (D1.1, D2.3, …)
- Expected outcomes
- Keywords / research areas
- Budget breakdown
- Timeline estimates
- Evaluation criteria
- Eligibility details
- Opening date
- Duration estimate

All extraction is regex/heuristic-based — no NLP, no external APIs, no PDFs.
"""

import re
import logging

logger = logging.getLogger("extractor")


# ─────────────────────────────────────────────────────────────────────────────
# Budget parsing
# ─────────────────────────────────────────────────────────────────────────────

def extract_budget(call: dict) -> dict:
    """Parse budget string and scope text into structured budget info."""
    budget_str = call.get("BUDGET", "") or ""
    scope = call.get("SCOPE", "") or ""
    text = budget_str + " " + scope

    result = {
        "budget_total": "",
        "budget_per_project": "",
        "grants": "",
        "currency": "EUR",
    }

    # Total budget: "€45M total", "EUR 45 000 000", "~€20M", "budget of EUR 30 million"
    total_patterns = [
        r'(?:total\s+(?:indicative\s+)?budget|indicative\s+budget)[:\s]+(?:EUR\s*|€\s*)?([0-9][0-9 ,\.]+)\s*(million|m\b|billion|b\b)?',
        r'(?:EUR\s*|€\s*)([0-9][0-9 ,\.]+)\s*(million|m\b|billion|b\b)?\s*(?:total|overall)',
        r'~?(?:EUR\s*|€\s*)([0-9][0-9 ,\.]+)\s*(M|m|million|billion|B|b)\s*(?:total|·)',
        r'(?:budget|funding)[:\s]+~?(?:EUR\s*|€\s*)([0-9][0-9 ,\.]+)\s*(million|m\b|M\b)?',
    ]
    for pat in total_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            num = m.group(1).replace(" ", "").replace(",", "")
            unit = (m.group(2) or "").lower()
            if unit.startswith("m") or unit == "m":
                result["budget_total"] = f"€{num}M"
            elif unit.startswith("b"):
                result["budget_total"] = f"€{num}B"
            else:
                try:
                    n = float(num)
                    if n > 100000:
                        result["budget_total"] = f"€{n/1000000:.0f}M"
                    else:
                        result["budget_total"] = f"€{num}"
                except ValueError:
                    result["budget_total"] = f"€{num}"
            break

    if not result["budget_total"] and budget_str:
        result["budget_total"] = budget_str.strip()

    # Per-project budget: "€4-5M per project", "€8M/proyecto", "EUR 3 to 5 million per project"
    per_proj_patterns = [
        r'(?:EUR\s*|€\s*)([0-9][0-9 ,\.\-–]+)\s*(million|m\b|M\b)?\s*(?:/proyecto|per\s+project|/project)',
        r'([0-9][0-9 ,\.\-–]+)\s*(million|m\b|M\b)\s*(?:/proyecto|per\s+project)',
        r'(?:EUR\s*|€\s*)([0-9][0-9 ,\.\-–]+)\s*(?:to|[-–])\s*(?:EUR\s*|€\s*)?([0-9][0-9 ,\.]+)\s*(million|m\b|M\b)',
    ]
    for pat in per_proj_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(0)
            # Clean up
            raw = re.sub(r'\s+', ' ', raw).strip()
            if 'million' in raw.lower() or 'm' in raw.lower().split()[-1:]:
                nums = re.findall(r'[0-9][0-9 ,\.]*', raw)
                if len(nums) >= 2:
                    result["budget_per_project"] = f"€{nums[0].strip()}M - €{nums[1].strip()}M"
                elif nums:
                    result["budget_per_project"] = f"€{nums[0].strip()}M"
            break

    # Number of grants: "6 proyectos", "5 projects", "up to 3 grants"
    grants_m = re.search(r'(\d+)\s*(?:proyectos?|projects?|grants?)', text, re.IGNORECASE)
    if grants_m:
        result["grants"] = grants_m.group(1)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Action / Project type
# ─────────────────────────────────────────────────────────────────────────────

_ACTION_MAP = {
    "RIA": "Research & Innovation Action",
    "IA": "Innovation Action",
    "CSA": "Coordination & Support Action",
    "PCP": "Pre-Commercial Procurement",
    "PPI": "Public Procurement of Innovation",
    "MSCA": "Marie Skłodowska-Curie Action",
    "EIC": "EIC Accelerator",
    "ERC": "ERC Grant",
}


def extract_action_type(call: dict) -> str:
    """Determine the action type code (RIA, IA, CSA, etc.)."""
    action = (call.get("ACTION", "") or "").upper()
    budget = (call.get("BUDGET", "") or "").upper()
    call_id = (call.get("ID", "") or "").upper()
    title = (call.get("TÍTULO", "") or "").upper()

    for code in ("RIA", "IA", "CSA", "PCP", "PPI", "MSCA", "EIC", "ERC"):
        if code in action:
            return code
        if f"-{code}-" in call_id or call_id.endswith(f"-{code}"):
            return code

    # Check title: "(RIA)", "(IA)", "(CSA)"
    for code in ("RIA", "IA", "CSA"):
        if f"({code})" in title or f" {code} " in f" {title} ":
            return code

    # Check budget string: "· RIA", "· IA"
    for code in ("RIA", "IA", "CSA"):
        if f"· {code}" in budget or f"·{code}" in budget.replace(" ", ""):
            return code

    # Scope-based fallback
    scope = (call.get("SCOPE", "") or "").lower()
    if "research and innovation action" in scope or "research & innovation action" in scope:
        return "RIA"
    if "innovation action" in scope and "research" not in scope:
        return "IA"
    if "coordination and support" in scope or "coordination & support" in scope:
        return "CSA"

    return "RIA"  # default


# ─────────────────────────────────────────────────────────────────────────────
# Duration estimate
# ─────────────────────────────────────────────────────────────────────────────

def extract_duration(call: dict) -> int:
    """Estimate project duration in months from scope text or action type."""
    scope = (call.get("SCOPE", "") or "")

    # Explicit mention: "36 months", "48-month", "3 years"
    m = re.search(r'(\d{1,3})\s*[-–]?\s*months?', scope, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r'(\d{1,2})\s*years?', scope, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 12

    # Default by action type
    action = extract_action_type(call)
    defaults = {"RIA": 36, "IA": 36, "CSA": 24, "MSCA": 48, "ERC": 60}
    return defaults.get(action, 36)


# ─────────────────────────────────────────────────────────────────────────────
# Expected outcomes
# ─────────────────────────────────────────────────────────────────────────────

def extract_expected_outcomes(scope: str) -> list[str]:
    """Extract expected outcomes / key objectives from scope text."""
    if not scope:
        return []

    outcomes = []

    # Split into meaningful lines/sentences
    lines = scope.split("\n")
    # Also try splitting on semicolons and periods for dense text
    expanded = []
    for line in lines:
        parts = re.split(r'(?<=[.;])\s+', line)
        expanded.extend(parts)

    for line in expanded:
        line = line.strip()
        if not line or len(line) < 35 or len(line) > 300:
            continue

        # Clean bullet prefixes
        clean = re.sub(r'^[-•*▸▪▷→·]\s*', '', line)
        clean = re.sub(r'^\d+[.)]\s*', '', clean)
        clean = clean.strip()

        if len(clean) < 35 or len(clean) > 280:
            continue

        # Skip header-like lines
        if re.match(r'^(the\s+call|this\s+call|horizon\s|eu\s+fund|please\s|note:|important:|background:|legal\s+entities)', clean, re.IGNORECASE):
            continue
        if re.match(r'^[A-Z\s]{10,}$', clean):
            continue

        outcomes.append(clean[0].upper() + clean[1:])

    return outcomes[:10]


# ─────────────────────────────────────────────────────────────────────────────
# Keywords / Research areas
# ─────────────────────────────────────────────────────────────────────────────

_TECH_KEYWORDS = [
    "Artificial Intelligence", "Machine Learning", "Deep Learning", "Neural Network",
    "Natural Language Processing", "Computer Vision", "Cybersecurity", "Blockchain",
    "Quantum Computing", "Digital Twin", "Edge Computing", "Cloud Computing",
    "Big Data", "Autonomous Systems", "Internet of Things", "5G", "6G",
    "Renewable Energy", "Carbon Neutrality", "Climate Change", "Precision Agriculture",
    "Genomics", "Proteomics", "Smart Grid", "Electric Vehicle", "Autonomous Vehicle",
    "Robotics", "Photonics", "Semiconductors", "Advanced Materials", "Nanotechnology",
    "Biotechnology", "Remote Sensing", "Satellite", "GIS", "Data Analytics",
    "Digital Infrastructure", "Federated Learning", "Data Spaces", "Open Source",
    "Smart City", "eHealth", "Telemedicine", "Circular Economy", "Green Hydrogen",
    "Battery Technology", "Wind Energy", "Solar Energy", "Carbon Capture",
    "Biodiversity", "Sustainable Agriculture", "Food Safety", "Water Management",
]


def extract_keywords(scope: str) -> list[str]:
    """Extract research area keywords from scope text."""
    if not scope:
        return []

    found = []
    seen = set()
    sl = scope.lower()

    # 1. Check known technology keywords
    for kw in _TECH_KEYWORDS:
        if kw.lower() in sl and kw not in seen:
            found.append(kw)
            seen.add(kw)

    # 2. Multi-word capitalized phrases (research topics)
    skip = {
        "The Call", "This Call", "This Action", "Member States", "European Union",
        "Horizon Europe", "Work Programme", "Project Results", "Expected Outcomes",
        "Legal Entities", "Innovation Actions", "Research Actions",
        "General Annex", "General Annexes",
    }
    caps = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}', scope)
    for phrase in caps:
        if phrase not in skip and phrase not in seen and len(phrase) < 40:
            found.append(phrase)
            seen.add(phrase)

    return found[:14]


# ─────────────────────────────────────────────────────────────────────────────
# Work packages
# ─────────────────────────────────────────────────────────────────────────────

def extract_work_packages(scope: str) -> list[dict]:
    """Extract work package references from scope text."""
    if not scope:
        return []

    wps = []
    seen = set()

    # Pattern 1: WP1: Title or WP 1 - Title
    for m in re.finditer(r'\bWP\s*(\d+)\s*[:\-–]\s*([^\n;.]{8,100})', scope, re.IGNORECASE):
        num = f"WP{m.group(1)}"
        if num not in seen:
            wps.append({"id": num, "title": m.group(2).strip()})
            seen.add(num)

    # Pattern 2: Work Package N: Title
    if not wps:
        for m in re.finditer(r'Work\s+Package\s+(\d+)\s*[:\-–]\s*([^\n;.]{8,100})', scope, re.IGNORECASE):
            num = f"WP{m.group(1)}"
            if num not in seen:
                wps.append({"id": num, "title": m.group(2).strip()})
                seen.add(num)

    return wps


# ─────────────────────────────────────────────────────────────────────────────
# Deliverables
# ─────────────────────────────────────────────────────────────────────────────

def extract_deliverables(scope: str) -> list[dict]:
    """Extract deliverable references from scope text."""
    if not scope:
        return []

    delivs = []
    seen = set()

    # Pattern 1: D1.1: Title or D1: Title
    for m in re.finditer(r'\bD(\d+(?:\.\d+)?)\s*[:\-–]\s*([^\n;.]{8,100})', scope):
        num = f"D{m.group(1)}"
        if num not in seen:
            delivs.append({"id": num, "title": m.group(2).strip(), "due": ""})
            seen.add(num)

    # Pattern 2: Deliverable N: Title
    if not delivs:
        for m in re.finditer(r'Deliverable\s+(\d+(?:\.\d+)?)\s*[:\-–]\s*([^\n;.]{8,100})', scope, re.IGNORECASE):
            num = f"D{m.group(1)}"
            if num not in seen:
                delivs.append({"id": num, "title": m.group(2).strip(), "due": ""})
                seen.add(num)

    # Try to extract due dates: "due M12", "month 24"
    for d in delivs:
        pat = re.compile(
            re.escape(d["id"]) + r'.*?(?:due|month|M)\s*(\d+)',
            re.IGNORECASE
        )
        m = pat.search(scope)
        if m:
            d["due"] = f"M{m.group(1)}"

    return delivs


# ─────────────────────────────────────────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────────────────────────────────────────

def extract_timeline(call: dict) -> dict:
    """Build a full timeline dict from call fields and estimated dates."""
    deadline = call.get("DEADLINE", "") or ""
    scope = call.get("SCOPE", "") or ""
    duration = extract_duration(call)

    # Try to parse opening date from scope
    opening = ""
    m = re.search(r'open(?:ing|s?)\s*(?:date)?[:\s]+(\d{4}[-/]\d{2}[-/]\d{2})', scope, re.IGNORECASE)
    if m:
        opening = m.group(1).replace("/", "-")

    timeline = {
        "opening": opening,
        "submission": deadline,
        "evaluation_start": "",
        "evaluation_end": "",
        "grant_agreement": "",
        "project_start": "",
        "project_end": "",
        "duration_months": duration,
    }

    # If we have a deadline, estimate downstream dates
    if deadline and re.match(r'\d{4}-\d{2}-\d{2}', deadline):
        try:
            from datetime import datetime, timedelta
            dl = datetime.strptime(deadline[:10], "%Y-%m-%d")

            timeline["evaluation_start"] = (dl + timedelta(days=30)).strftime("%Y-%m-%d")
            timeline["evaluation_end"] = (dl + timedelta(days=150)).strftime("%Y-%m-%d")
            timeline["grant_agreement"] = (dl + timedelta(days=210)).strftime("%Y-%m-%d")

            project_start = dl + timedelta(days=270)
            timeline["project_start"] = project_start.strftime("%Y-%m-%d")

            project_end = project_start + timedelta(days=duration * 30)
            timeline["project_end"] = project_end.strftime("%Y-%m-%d")
        except (ValueError, ImportError):
            pass

    return timeline


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation criteria
# ─────────────────────────────────────────────────────────────────────────────

def extract_evaluation_criteria(call: dict) -> dict:
    """Determine evaluation criteria weights based on action type."""
    action = extract_action_type(call)
    scope = (call.get("SCOPE", "") or "").lower()

    # Try to find explicit weights in scope
    criteria = {}
    for name in ("excellence", "impact", "implementation", "quality"):
        m = re.search(name + r'\s*[:\-–]?\s*(\d+)\s*%', scope)
        if m:
            criteria[name] = int(m.group(1))

    if criteria:
        return criteria

    # Default by action type (Horizon Europe standard)
    defaults = {
        "RIA": {"excellence": 50, "impact": 30, "implementation": 20},
        "IA":  {"excellence": 30, "impact": 30, "implementation": 40},
        "CSA": {"excellence": 50, "impact": 30, "implementation": 20},
        "ERC": {"excellence": 100, "impact": 0, "implementation": 0},
        "EIC": {"excellence": 50, "impact": 40, "implementation": 10},
    }
    return defaults.get(action, {"excellence": 50, "impact": 30, "implementation": 20})


# ─────────────────────────────────────────────────────────────────────────────
# Eligibility
# ─────────────────────────────────────────────────────────────────────────────

def extract_eligibility(call: dict) -> dict:
    """Extract eligibility details from scope text."""
    scope = (call.get("SCOPE", "") or "").lower()

    # Countries
    if "associated countr" in scope:
        countries = "EU Member States + Associated Countries"
    elif "third countr" in scope:
        countries = "EU + Third Countries (conditions apply)"
    else:
        countries = "EU Member States + Associated Countries"

    # China restriction (common in Cluster 4)
    china_restricted = "china" in scope and ("not eligible" in scope or "restriction" in scope)

    # Organization types
    org_types = []
    if "sme" in scope or "small and medium" in scope:
        org_types.append("SMEs")
    if "universit" in scope or "academ" in scope or "higher education" in scope:
        org_types.append("Universities")
    if "research organ" in scope or "research center" in scope or "research institute" in scope:
        org_types.append("Research Organizations")
    if "industri" in scope or "enterprise" in scope or "compan" in scope:
        org_types.append("Industry")
    if "public bod" in scope or "government" in scope or "authorit" in scope:
        org_types.append("Public Bodies")
    if "ngo" in scope or "civil society" in scope or "non-governmental" in scope:
        org_types.append("NGOs")
    if "hospital" in scope or "clinical" in scope:
        org_types.append("Healthcare providers")
    if not org_types:
        org_types = ["Universities", "Research Organizations", "SMEs", "Industry"]

    # Consortium
    if "individual" in scope or "solo" in scope or "single applicant" in scope:
        consortium_required = False
        consortium_type = "Solo applications allowed"
    elif "single beneficiar" in scope:
        consortium_required = False
        consortium_type = "Single beneficiary possible"
    else:
        consortium_required = True
        consortium_type = "Multi-partner consortium required"

    return {
        "countries": countries,
        "china_restricted": china_restricted,
        "org_types": org_types,
        "consortium_required": consortium_required,
        "consortium_type": consortium_type,
        "roles": ["Coordinator", "Partner"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cluster extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_cluster(call: dict) -> str:
    """Extract the Horizon Europe cluster number from call ID or cluster field."""
    call_id = call.get("ID", "") or ""
    cluster_field = call.get("CLUSTER", "") or ""

    # From ID: HORIZON-CL4-... → "4"
    m = re.search(r'HORIZON-CL(\d)', call_id)
    if m:
        return m.group(1)

    # From cluster field: "Cluster 4 — Digital" → "4"
    m = re.search(r'Cluster\s+(\d)', cluster_field)
    if m:
        return m.group(1)

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Master enrichment function
# ─────────────────────────────────────────────────────────────────────────────

def enrich_call(call: dict) -> dict:
    """Enrich a call dict with all extracted structured data.

    Takes a call dict with at minimum: ID, SCOPE, BUDGET, ACTION, DEADLINE.
    Returns a new dict with all the enriched fields added.

    This is the main entry point — call it for each call in top_10.
    """
    try:
        scope = call.get("SCOPE", "") or ""
        call_id = call.get("ID", "") or ""

        budget_info = extract_budget(call)
        action_code = extract_action_type(call)
        action_label = _ACTION_MAP.get(action_code, action_code)
        duration = extract_duration(call)
        timeline = extract_timeline(call)
        criteria = extract_evaluation_criteria(call)
        eligibility = extract_eligibility(call)
        outcomes = extract_expected_outcomes(scope)
        keywords = extract_keywords(scope)
        wps = extract_work_packages(scope)
        deliverables = extract_deliverables(scope)
        cluster = extract_cluster(call)

        enriched = {
            # Core fields (pass through from call)
            "id": call_id,
            "title": call.get("TÍTULO", call.get("title", "")),
            "status": call.get("status", call.get("ESTADO", "")),
            "deadline": call.get("deadline", call.get("DEADLINE", "")),
            "score": call.get("score", 0),
            "sector_match": call.get("sector_match", "none"),
            "call_sector": call.get("call_sector", "UNKNOWN"),
            "scope": scope,

            # Enriched fields
            "action": action_code,
            "action_label": action_label,
            "opening_date": timeline["opening"],
            "duration_months": duration,

            # Budget
            "budget": call.get("BUDGET", call.get("budget", "")),
            "budget_total": budget_info["budget_total"],
            "budget_per_project": budget_info["budget_per_project"],
            "grants": budget_info["grants"],

            # Structured extractions
            "expected_outcomes": outcomes,
            "work_packages": wps,
            "deliverables": deliverables,
            "keywords": keywords,

            # Timeline
            "timeline": timeline,

            # Evaluation
            "evaluation_criteria": criteria,

            # Eligibility
            "eligibility": eligibility,

            # Classification
            "cluster": cluster,
        }

        logger.debug(
            f"Enriched {call_id}: outcomes={len(outcomes)}, "
            f"keywords={len(keywords)}, wps={len(wps)}, delivs={len(deliverables)}"
        )

        return enriched

    except Exception as exc:
        logger.error(f"Failed to enrich call {call.get('ID', '?')}: {exc}", exc_info=True)
        # Return call as-is with empty enrichment
        return {
            "id": call.get("ID", call.get("id", "?")),
            "title": call.get("TÍTULO", call.get("title", "")),
            "status": call.get("status", call.get("ESTADO", "")),
            "deadline": call.get("deadline", call.get("DEADLINE", "")),
            "score": call.get("score", 0),
            "sector_match": call.get("sector_match", "none"),
            "call_sector": call.get("call_sector", "UNKNOWN"),
            "scope": call.get("SCOPE", call.get("scope", "")),
            "action": "",
            "action_label": "",
            "opening_date": "",
            "duration_months": 36,
            "budget": call.get("BUDGET", call.get("budget", "")),
            "budget_total": "",
            "budget_per_project": "",
            "grants": "",
            "expected_outcomes": [],
            "work_packages": [],
            "deliverables": [],
            "keywords": [],
            "timeline": {},
            "evaluation_criteria": {"excellence": 50, "impact": 30, "implementation": 20},
            "eligibility": {},
            "cluster": "",
        }

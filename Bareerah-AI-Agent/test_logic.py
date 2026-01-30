
def is_negative_token(text):
    NEGATIVE_TOKENS_EN = {"is", "no", "yes", "ok", "okay", "right", "here", "there", "that", "this", "sure", "please", "again", "maybe", "yeah", "uh", "um", "hmm", "alright", "fine", "done", "go", "ahead"}
    return text.lower().strip() in NEGATIVE_TOKENS_EN

def is_generic_location(text):
    GENERIC_WORDS_EN = {"location", "airport", "mall", "here", "there", "this", "that", "yes", "no", "ok", "okay", "right", "sure", "maybe"}
    return text.lower().strip() in GENERIC_WORDS_EN

def has_geo_marker_current(text):
    GEO_MARKERS = {"airport", "mall", "tower", "street", "road", "avenue", "hotel", "terminal", "marina", "downtown", "city"}
    text_lower = text.lower()
    return any(marker in text_lower for marker in GEO_MARKERS)

def has_geo_marker_new(text):
    # Added many more Dubai-specific and general location markers
    GEO_MARKERS = {
        "airport", "mall", "tower", "street", "road", "avenue", "hotel", "terminal", "marina", "downtown", "city",
        "residence", "village", "jvc", "jlt", "palm", "beach", "park", "souq", "market", "university", "college",
        "school", "hospital", "clinic", "metro", "station", "stop", "area", "zone", "cluster", "block", "house",
        "villa", "apartment", "burj", "khalifa", "frame", "museum", "opera", "atlantis", "garden", "resort",
        "palace", "creek", "harbour", "hills", "meadows", "springs", "lakes", "island", "world", "canal",
        "gate", "center", "centre", "plaza", "square", "court", "heights", "views", "oasis", "silicon",
        "media", "internet", "studio", "sports", "motor", "investment", "business", "bay", "walk", "residences",
        "suites", "inn", "restaurant", "cafe", "club", "gym", "cinema", "theatre", "stadium", "arena"
    }
    text_lower = text.lower()
    return any(marker in text_lower for marker in GEO_MARKERS)

def validate_location(text, strategy="current"):
    if not text: return False, "Empty"
    if is_negative_token(text): return False, "Negative Token"
    if is_generic_location(text): return False, "Generic Location"
    
    # Verb check (simplified from main.py)
    verb_only = {"go", "come", "need", "want", "take"}
    if text.lower().strip() in verb_only: return False, "Verb Only"
    
    has_marker = False
    if strategy == "current":
        has_marker = has_geo_marker_current(text)
    else:
        has_marker = has_geo_marker_new(text)
        
    if not has_marker: return False, "No Geo Marker"
    
    return True, "Valid"

# Test Cases
test_locations = [
    "Dubai Mall", "Burj Khalifa", "JVC", "International City", 
    "My home", "Palm Jumeirah", "JLT Cluster V", "Terminal 3",
    "Novotel Hotel", "Marina Walk", "Business Bay", "Silicon Oasis",
    "Global Village", "Dubai Frame", "Atlantis The Palm",
    "Some random street", "Near the park", "Union Metro Station"
]

print("--- TESTING CURRENT LOGIC ---")
for loc in test_locations:
    valid, reason = validate_location(loc, strategy="current")
    status = "✅" if valid else "❌"
    print(f"{status} {loc:<25} -> {reason}")

print("\n--- TESTING NEW LOGIC ---")
for loc in test_locations:
    valid, reason = validate_location(loc, strategy="new")
    status = "✅" if valid else "❌"
    print(f"{status} {loc:<25} -> {reason}")

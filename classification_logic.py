# classification_logic.py

"""
Advanced, sexuality-first video classification logic.
Now includes title and channel name analysis.
"""
# --- Keyword Maps (for secondary descriptive tags) ---
GENRE_MAP = {'pov': 'POV', 'point of view': 'POV', 'public': 'Public', 'interview': 'Interview', 'reality': 'Reality', 'compilation': 'Compilation', 'behind the scenes': 'Behind the Scenes'}
ETHNICITY_MAP = {'ebony': 'Ebony', 'black': 'Ebony', 'asian': 'Asian', 'latina': 'Latina', 'latino': 'Latina', 'indian': 'Indian'}
ATTRIBUTE_MAP = {'teen': 'Teen', 'young': 'Teen', 'milf': 'MILF', 'mature': 'Mature', 'cougar': 'MILF', 'big tits': 'Big Tits', 'big boobs': 'Big Tits', 'small tits': 'Small Tits', 'big ass': 'Big Ass', 'bubble butt': 'Big Ass', 'blonde': 'Blonde', 'brunette': 'Brunette', 'redhead': 'Redhead', 'tattoo': 'Tattoo', 'hairy': 'Hairy', 'amateur': 'Amateur', 'homemade': 'Amateur', 'hd': 'HD', '4k': 'HD'}
ACTION_MAP = {'anal': 'Anal', 'dp': 'DP', 'double penetration': 'DP', 'creampie': 'Creampie', 'deepthroat': 'Deepthroat', 'facial': 'Facial', 'bdsm': 'BDSM', 'bondage': 'BDSM', 'femdom': 'Femdom', 'fisting': 'Fisting', 'footjob': 'Foot Fetish', 'feet': 'Foot Fetish', 'handjob': 'Handjob', 'pegging': 'Pegging', 'rimjob': 'Rimjob', 'squirting': 'Squirting', 'tribbing': 'Tribbing', 'scissoring': 'Scissoring', 'pussy licking': 'Pussy Licking'}


def determine_sexuality(male_count, female_count, trans_count, title, channel_name, tags):
    """
    Determines the single, most precise sexuality tag based on a strict hierarchy.
    """
    total_actors = male_count + female_count + trans_count
    tags_lower = {tag.lower() for tag in tags}
    title_lower = title.lower()
    channel_lower = channel_name.lower()

    # --- Hierarchy of Sexuality Determination ---

    # 1. Trans is highest priority, check actors first, then title/channel
    if trans_count > 0:
        if trans_count == 1 and female_count > 0 and male_count == 0: return "Trans (T/F)"
        if trans_count == 1 and male_count > 0 and female_count == 0: return "Trans (T/M)"
        if trans_count > 0 and male_count > 0 and female_count > 0: return "Trans Group"
        return "Trans"
    if 'trans' in title_lower or 'transgender' in title_lower or 'trans' in channel_lower:
        return "Trans"

    # 2. Group scenes (by actor count)
    if total_actors >= 5:
        if male_count == 0: return "Orgy (All-Female)"
        if female_count == 0: return "Orgy (All-Male)"
        return "Orgy (Mixed)"
    
    if total_actors == 4:
        if female_count == 4: return "Foursome (FFFF)"
        if male_count == 4: return "Foursome (MMMM)"
        if female_count == 3 and male_count == 1: return "Foursome (FFFM)"
        if male_count == 3 and female_count == 1: return "Foursome (MMMF)"
        if female_count == 2 and male_count == 2: return "Foursome (FFMM)"
        return "Foursome"

    if total_actors == 3:
        if female_count == 3: return "Threesome (FFF)"
        if male_count == 3: return "Threesome (MMM)"
        if female_count == 2 and male_count == 1: return "Threesome (FFM)"
        if male_count == 2 and female_count == 1: return "Threesome (MMF)"
        if any(k in tags_lower for k in ["ffm", "f/f/m", "mff"]): return "Threesome (FFM)"
        if any(k in tags_lower for k in ["mmf", "m/m/f"]): return "Threesome (MMF)"
        return "Threesome"

    # 3. Couple scenes (by actor count)
    if total_actors == 2:
        if female_count == 2: return "Lesbian (F/F)"
        if male_count == 2: return "Gay (M/M)"
        if male_count == 1 and female_count == 1: return "Straight (M/F)"

    # 4. Solo scenes (by actor count)
    if total_actors == 1:
        if female_count == 1: return "Solo (Female)"
        if male_count == 1: return "Solo (Male)"

    # 5. Fallback to title/channel if no actor data
    if 'lesbian' in title_lower or 'lesbian' in channel_lower: return "Lesbian"
    if 'gay' in title_lower or 'gay' in channel_lower: return "Gay"
    if 'straight' in title_lower: return "Straight"

    # 6. Final fallback to generic tags
    if "lesbian" in tags_lower or "girl on girl" in tags_lower: return "Lesbian"
    if "gay" in tags_lower: return "Gay"
    if "straight" in tags_lower: return "Straight"

    return "Uncategorized"

def classify_video(title, channel_name, scraped_tags, male_actors, female_actors, trans_actors):
    """
    Generates a final list of tags, with the primary sexuality tag ALWAYS first.
    """
    male_count = len(male_actors)
    female_count = len(female_actors)
    trans_count = len(trans_actors)

    primary_sexuality_tag = determine_sexuality(male_count, female_count, trans_count, title, channel_name, scraped_tags)
    
    secondary_tags = set()
    search_text = " ".join(scraped_tags) + " " + title.lower()
    all_maps = {**GENRE_MAP, **ETHNICITY_MAP, **ATTRIBUTE_MAP, **ACTION_MAP}

    for keyword, tag in all_maps.items():
        if keyword in search_text:
            secondary_tags.add(tag)
            
    final_tags = [primary_sexuality_tag]
    
    primary_base = primary_sexuality_tag.split(' ')[0]
    for tag in sorted(list(secondary_tags)):
        if tag.lower() not in primary_base.lower():
            final_tags.append(tag)
            
    return final_tags
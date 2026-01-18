import feedparser
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
import json
import time
import schedule
from datetime import datetime
import os
import dateutil.parser

# Configuration
# Google News RSS allows searching. We will use multiple specific queries.
BASE_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=mr-IN&gl=IN&ceid=IN:mr"

QUERIES = [
    "Latur OR Latur District when:3d",
    "Udgir OR Ausa OR Nilanga OR Ahmedpur when:3d", # Major Tehsils
    "site:lokmat.com Latur OR Udgir OR Ausa when:3d",
    "site:esakal.com Latur OR Udgir OR Ausa when:3d",
    "site:divyamarathi.bhaskar.com Latur when:3d",
    "site:abpmajha.abplive.in Latur when:3d",
    "site:loksatta.com Latur when:3d",
    "site:maharashtratimes.com Latur when:3d",
    "site:tv9marathi.com Latur when:3d",
    "site:samna.asia Latur when:3d"
]

JSON_FILE = "news_data.json"
TRANSLATOR = Translator(timeout=10)

def fetch_and_process_news():
    print(f"[{datetime.now()}] Checking for news from multiple sources...")
    all_entries = []
    
    # Fetch from all queries
    for query in QUERIES:
        try:
            formatted_url = BASE_RSS_URL.format(query=requests.utils.quote(query))
            print(f"Fetching: {query}")
            feed = feedparser.parse(formatted_url)
            all_entries.extend(feed.entries)
        except Exception as e:
            print(f"Error fetching {query}: {e}")

    news_items = []
    seen_titles = set()

    # Sort entries by published date (newest first)
    # Default sorting might be mixed, so let's try to sort if parsed_published exists
    # If not, we rely on feed order (usually relevant)
    
    for entry in all_entries:
        # Basic info
        title = entry.title
        link = entry.link


        if title in seen_titles:
            continue
        seen_titles.add(title)

        # Parse date to ensure it's today's news
        pub_date_str = entry.published
        try:
            dt = dateutil.parser.parse(pub_date_str)
            # Global filter: Only show news from Today (local time approx)
            # Keeping it loose as per previous logic
            pass
        except Exception as e:
            # print(f"Date parsing error: {e}")
            pass

        # Extract Image (Thumbnail)
        image_url = "https://via.placeholder.com/300x200?text=Latur+News"
        try:
           # Check if description has an image
            soup_desc = BeautifulSoup(entry.summary, "html.parser")
            img_tag = soup_desc.find('img')
            if img_tag and 'src' in img_tag.attrs:
                image_url = img_tag['src']
        except Exception as e:
            # print(f"Image extraction error: {e}")
            pass

        # Description cleanup
        description = BeautifulSoup(entry.summary, "html.parser").get_text()

        # Translation Logic
        try:
            # Detect language. If not Marathi, translate.
            # We concat title and description for better detection context
            full_text = f"{title} {description}"
            detected = TRANSLATOR.detect(full_text)
            
            if detected.lang != 'mr':
                # Translate Title
                title = TRANSLATOR.translate(title, dest='mr').text
                # Translate Description (truncate if too long to save API/time)
                description = TRANSLATOR.translate(description[:500], dest='mr').text
        except Exception as e:
            # Fallback: keep original text if translation fails
            # print(f"Translation warning for '{title[:20]}...': {e}")
            pass

        # STRICT FILTER CHECK
        # We check both positive keywords (Must Have) and negative keywords (Must Not Have if no Latur)
        check_text = (title + " " + description).lower()
        
        # 1. Positive Keywords: Must contain at least one of these
        positive_keywords = [
            "latur", "laatur", "लातूर",
            "udgir", "उदगीर",
            "ausa", "औसा",
            "nilanga", "निलंगा",
            "ahmedpur", "अहमदपूर",
            "chakur", "चाकूर",
            "renapur", "रेणापूर",
            "shirur anantpal", "shirur-anantpal",
            "deoni", "devni",
            "jalkot"
        ]
        
        if not any(k in check_text for k in positive_keywords):
            continue

        # 2. Negative Keywords: Exclude if these unrelated places are mentioned AND "Latur" is not the main focus.
        # This helps avoid "Statewide news" that mentions 10 districts including Latur, or false positives.
        # Actually, user wants STRICT Latur news. 
        # So if it mentions "Pune" or "Mumbai" heavily but Latur is just a tag, we might want to keep it IF it's about Latur.
        # But if it's "Pune Election Results" and Latur is not mentioned, looking at the previous logic, it shouldn't have passed?
        # Aah, "Latur" might be in the 'source' or hidden metadata we don't see, or Google Search is fuzzy.
        # Let's add an explicit exclude for other district headers if Latur is not in the TITLE.

        # Refined Logic: If Title mentions another District but NOT Latur, skip it.
        # (This prevents "Pune News" appearing just because "Latur" was in the description footer)
        
        other_districts = [
            "pune", "mumbai", "nashik", "aurangabad", "sambhajinagar", "nagpur", 
            "kolhapur", "solapur", "sangli", "satara", "thane", "palghar", 
            "dhule", "jalgaon", "nanded", "parbhani", "beed", "hingoli", "jalna",
            "amravati", "akola", "yavatmal", "washim", "bhandara", "gondia", "chandrapur", "gadchiroli",
            "raigad", "ratnagiri", "sindhudurg", "dharashiv", "osmanabad"
        ]

        title_lower = title.lower()
        
        # If title is heavily about another district and doesn't mention Latur, skip.
        is_about_other = any(d in title_lower for d in other_districts)
        is_about_latur_title = any(k in title_lower for k in positive_keywords)
        
        if is_about_other and not is_about_latur_title:
             continue


        news_items.append({
            "title": title,
            "link": link,
            "date": pub_date_str, # Keep original string for display
            "image": image_url,
            "source": entry.source.title if 'source' in entry else "News Portal",
            "description": description
        })

    # Save to JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(news_items, f, ensure_ascii=False, indent=4)
    
    print(f"[{datetime.now()}] Successfully updated {len(news_items)} news items.")


def run_scheduler():
    # Run immediately once
    fetch_and_process_news()
    
    # Schedule every 30 minutes
    schedule.every(30).minutes.do(fetch_and_process_news)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("Starting Latur Live News Fetcher...")
    run_scheduler()

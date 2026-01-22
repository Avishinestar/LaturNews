import feedparser
import re
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
    "Latur District News when:1d",
    "Latur City News when:1d",
    # Tehsil specific - adding 'Latur' to ensure district relevance
    "Udgir Latur News when:1d",
    "Ausa Latur News when:1d",
    "Nilanga Latur News when:1d",
    "Ahmedpur Latur News when:1d",
    "Chakur Latur News when:1d",
    "Renapur Latur News when:1d",
    "Jalkot Latur News when:1d", 
    "Shirur Anantpal Latur News when:1d",
    "Deoni Latur News when:1d",
    # Specific Portals
    "site:lokmat.com Latur when:1d",
    "site:esakal.com Latur when:1d",
    "site:pudhari.news Latur when:1d",
    "site:saamana.com Latur when:1d",
    "site:tv9marathi.com Latur when:1d",
    "site:abpmajha.abplive.in Latur when:1d",
    "site:news18.com Latur when:1d",
    "site:zeenews.india.com Latur when:1d",
    "site:maharashtratimes.com Latur when:1d",
    "site:loksatta.com Latur when:1d",
    "site:divyamarathi.bhaskar.com Latur when:1d",
    "site:ekmat.com Latur when:1d",
    "site:public.app Latur when:1d",
    "Latur Samachar when:1d",
    # ePaper Queries
    "Lokmat ePaper Latur when:1d",
    "Esakal ePaper Latur when:1d",
    "Ekmat ePaper Latur when:1d",
    "Pudhari ePaper Latur when:1d",
    # New Portals
    "site:ndtv.com Latur when:1d",
    "site:saamtv.esakal.com Latur when:1d",
    "site:agrowon.esakal.com Latur when:1d",
    "site:sarkarnama.esakal.com Latur when:1d",
    "site:tarunbharat.com Latur when:1d",
    "site:deshonnati.com Latur when:1d",
    "site:jaimaharashtranews.com Latur when:1d",
    "site:maxmaharashtra.com Latur when:1d",
    "site:punyanagari.com Latur when:1d",
    "site:timesofindia.indiatimes.com Latur when:1d",
    "site:hindustantimes.com Latur when:1d",
    "site:aajlatur.com Latur when:1d"
]

# Strict Filter Keywords (Latur District Locations)
DISTRICT_KEYWORDS = [
    # English
    "Latur", "Udgir", "Ahmedpur", "Ausa", "Nilanga", "Renapur", 
    "Chakur", "Deoni", "Devni", "Shirur Anantpal", "Shirur-Anantpal", "Jalkot", "Jalkote",
    
    # Marathi
    "लातूर", "उदगीर", "अहमदपूर", "औसा", "निलंगा", "रेणापूर", 
    "चाकूर", "देवणी", "शिरूर अनंतपाळ", "शिरुर अनंतपाळ", "जळकोट"
]



SOURCE_DOMAINS = {
    "Lokmat": "lokmat.com",
    "Lokmat.com": "lokmat.com",
    "Lokmat ePaper": "lokmat.com",
    "Sakal": "esakal.com",
    "Esakal": "esakal.com",
    "Pudhari": "pudhari.news",
    "Pudhari News": "pudhari.news",
    "Saamana": "saamana.com",
    "TV9 Marathi": "tv9marathi.com",
    "ABP Majha": "marathi.abplive.com", 
    "News18": "news18.com",
    "News18 Lokmat": "news18.com",
    "news18marathi.com": "news18.com",
    "Zee News": "zeenews.india.com",
    "Zee 24 Taas": "zeenews.india.com",
    "Maharashtra Times": "maharashtratimes.com",
    "Loksatta": "loksatta.com",
    "Divya Marathi": "divyamarathi.bhaskar.com",
    "divyamarathi.bhaskar.com": "divyamarathi.bhaskar.com",
    "NDTV Marathi": "ndtv.com",
    "Agrowon": "agrowon.esakal.com",
    "Saam TV": "saamtv.esakal.com",
    "saamtv.esakal.com": "saamtv.esakal.com",
    "Tarun Bharat": "tarunbharat.com",
    "Deshonnati": "deshonnati.com",
    "Sarkarnama": "sarkarnama.esakal.com",
    "Jai Maharashtra": "jaimaharashtranews.com",
    "Max Maharashtra": "maxmaharashtra.com",
    "Punyanagari": "punyanagari.com",
    "Times of India": "timesofindia.indiatimes.com",
    "Hindustan Times": "hindustantimes.com",
    "Aaj Latur": "aajlatur.com",
    "Webdunia Marathi": "marathi.webdunia.com",
    "navarashtra.com": "navarashtra.com",
    "Pune Prime News": "puneprimenews.com",
    "Ekmat": "ekmat.com",
    "Ekmat ePaper": "ekmat.com",
    "Latur Samachar": "latursamachar.com",
    "Public App": "public.app",
    "Public.app": "public.app"
}

JSON_FILE = "news_data.json"
TRANSLATOR = Translator(timeout=10)

def is_relevant(text):
    """Check if text contains any district keyword using strict word boundaries."""
    if not text:
        return False
    text_lower = text.lower()
    
    for keyword in DISTRICT_KEYWORDS:
        # Check if keyword is ASCII (English) or Unicode (likely Marathi)
        if keyword.isascii():
            # For English, stick to strict word boundaries to avoid false positives (e.g. "Legislature")
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text_lower):
                return True
        else:
            # For Marathi, relax strict boundaries to catch inflections (e.g. "लातूरमध्ये", "लातूरचा")
            # Simple substring check is usually safe for these distinct place names
            if keyword.lower() in text_lower:
                return True
            
    return False

TRUSTED_SOURCES = [
    "Latur Samachar", "Aaj Latur", "Ekmat", "dainikekmat.com", "Public App", "Public.app", "Punyanagari", "punyanagari.com"
]

def fetch_and_process_news():
    print(f"[{datetime.now()}] Checking for news from multiple sources...")
    
    # Clear existing data to ensure no stale/unfiltered items remain if fetch fails
    if os.path.exists(JSON_FILE):
        try:
            os.remove(JSON_FILE)
            print("Cleared old news data.")
        except Exception as e:
            print(f"Warning: Could not clear old data: {e}")

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
            
        # Check source for trusted bypass
        source_title = entry.source.title if 'source' in entry else ""
        is_trusted = any(trusted in source_title for trusted in TRUSTED_SOURCES)

        # Strict Filtering: Check if title or link implies relevance
        # We can't check description effectively yet as it might need fetching/translating,
        # but let's check what we have (title).
        # We will also check description AFTER extraction/translation if needed, 
        # but filtering early saves processing.
        if not is_trusted and not is_relevant(title):
            # If title doesn't match, check description/summary
            # We extract description text early for checking
            temp_desc = BeautifulSoup(entry.summary, "html.parser").get_text() if 'summary' in entry else ""
            if not is_relevant(temp_desc):
                 # print(f"Skipping unrelated (Title & Desc mismatch): {title}")
                 continue

        seen_titles.add(title)

        # Parse date to ensure it's today's news
        pub_date_str = entry.published
        is_today = False
        try:
            dt = dateutil.parser.parse(pub_date_str)
            
            # Convert to local system time if it has timezone info
            if dt.tzinfo:
                dt = dt.astimezone() # Convert to local system time
                
            # Global filter: Only show news from Today (local time approx)
            if dt.date() == datetime.now().date():
                 is_today = True
        except Exception as e:
            # print(f"Date parsing error: {e}")
            pass
        
        if not is_today:
             continue

        # Extract Image (Thumbnail)
        image_url = ""
        is_logo = False
        
        try:
           # Check if description has an image
            soup_desc = BeautifulSoup(entry.summary, "html.parser")
            img_tag = soup_desc.find('img')
            if img_tag and 'src' in img_tag.attrs:
                image_url = img_tag['src']
        except Exception as e:
            # print(f"Image extraction error: {e}")
            pass
            
        # If no image found or it's a known pixel tracker (often 1x1), try source logo
        if not image_url or "tracker" in image_url or "pixel" in image_url:
            source_name = entry.source.title if 'source' in entry else ""
            # Try exact match or partial match
            domain = SOURCE_DOMAINS.get(source_name)
            if not domain:
                # Try to find a partial match manually
                for name, dom in SOURCE_DOMAINS.items():
                    if name.lower() in source_name.lower():
                        domain = dom
                        break
            
            if domain:
                image_url = f"https://logo.clearbit.com/{domain}"
                is_logo = True
            else:
                image_url = "https://via.placeholder.com/300x200?text=Latur+News"
                is_logo = False

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

        # Strict filtering already done on title.



        news_items.append({
            "title": title,
            "link": link,
            "date": pub_date_str, # Keep original string for display
            "image": image_url,
            "is_logo": is_logo,
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

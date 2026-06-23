import csv
import time
import requests
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import config

# List of target cities
TARGET_CITIES = [
    "Tampa FL", "Las Vegas NV", "Memphis TN", "Cleveland OH",
    "Greensboro NC", "Fresno CA", "Dallas TX", "Atlanta GA",
    "Chicago IL", "Houston TX"
]

# Free platforms patterns
FREE_PLATFORMS = ['weebly.com', 'wixsite.com', 'wix.com', 'squarespace.com', 'wordpress.com']

def get_places_from_google(query, api_key):
    """Searches Google Places API for churches."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print(f"Error fetching data from Google Places API: {e}")
        return []

def get_place_details(place_id, api_key):
    """Gets detailed info for a specific place like website and phone number."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,address_components,formatted_phone_number,website,url,user_ratings_total",
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {})
    except Exception as e:
        print(f"Error fetching place details: {e}")
        return {}

def check_website(url):
    """Checks if a website is working and parses it for email and Facebook link."""
    if not url:
        return "NO WEBSITE", None, None

    status = "WORKING"
    email = None
    facebook_url = None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Add timeout so it doesn't hang on broken sites
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            status = f"BROKEN ({response.status_code})"
        else:
            # Check for free platforms
            domain = urlparse(url).netloc
            for platform in FREE_PLATFORMS:
                if platform in domain:
                    status = "FREE PLATFORM"
                    break

            # Basic parsing for email and facebook
            soup = BeautifulSoup(response.text, "html.parser")

            # Find emails using regex
            emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}", response.text))
            # Filter out common false positives like image extensions
            emails = {e for e in emails if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'])}
            if emails:
                email = list(emails)[0]

            # Find Facebook link
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'facebook.com' in href:
                    facebook_url = href
                    break

    except requests.exceptions.RequestException as e:
        status = "BROKEN (Connection Error)"

    return status, email, facebook_url

def determine_priority(website_status):
    """Determines priority based on website status."""
    if website_status == "NO WEBSITE":
        return "HIGH"
    elif website_status.startswith("BROKEN"):
        return "URGENT"
    elif website_status == "FREE PLATFORM":
        return "MEDIUM"
    else:
        return "LOW"

def extract_city_state(address_components):
    """Extracts city and state from Google's address components."""
    city = ""
    state = ""
    for component in address_components:
        if "locality" in component.get("types", []):
            city = component.get("long_name", "")
        if "administrative_area_level_1" in component.get("types", []):
            state = component.get("short_name", "")
    return city, state

def main():
    api_key = config.GOOGLE_PLACES_API_KEY
    if api_key == "YOUR_API_KEY_HERE":
        print("Please set your Google Places API Key in config.py")
        return

    output_file = "churches_leads.csv"
    headers = [
        "Church Name", "Address", "City", "State", "Phone Number",
        "Email", "Website Status", "Facebook URL", "Google Maps URL", "PRIORITY"
    ]

    print(f"Starting Church Hunter...")
    print(f"Results will be saved to {output_file}\n")

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for location in TARGET_CITIES:
            print(f"Searching for churches in {location}...")
            query = f"churches in {location}"
            results = get_places_from_google(query, api_key)

            for place in results:
                place_id = place.get("place_id")
                if not place_id:
                    continue

                # Fetch details
                details = get_place_details(place_id, api_key)

                # Filter for small churches (under 500 reviews)
                reviews = details.get("user_ratings_total", 0)
                if reviews >= 500:
                    continue

                # Get information
                name = details.get("name", "")
                address = details.get("formatted_address", "")
                city, state = extract_city_state(details.get("address_components", []))
                phone = details.get("formatted_phone_number", "")
                maps_url = details.get("url", "")
                website = details.get("website", "")

                # Check website status and parse
                website_status, email, facebook_url = check_website(website)

                # If website is working, we might still want to skip if it's not a lead,
                # but the instructions say "marks NO WEBSITE as HIGH, BROKEN WEBSITE as URGENT, FREE PLATFORM (weebly/wix) as MEDIUM"
                # so we will include them.
                priority = determine_priority(website_status)

                # Save all results to CSV
                row = [
                    name, address, city, state, phone,
                    email if email else "",
                    website_status,
                    facebook_url if facebook_url else "",
                    maps_url,
                    priority
                ]
                writer.writerow(row)
                if priority != "LOW":
                    print(f"  -> Found Lead: {name} ({priority})")
                else:
                    print(f"  -> Checked: {name} (Working website)")
                f.flush() # Ensure it writes to disk immediately

                # Be nice to APIs
                time.sleep(1)

    print("\nFinished! Check churches_leads.csv for your leads.")

if __name__ == "__main__":
    main()

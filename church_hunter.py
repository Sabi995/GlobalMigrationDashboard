import os
import re
import csv
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urlparse

try:
    from config import GOOGLE_PLACES_API_KEY
except ImportError:
    print("Error: config.py not found. Please create it and add GOOGLE_PLACES_API_KEY.")
    GOOGLE_PLACES_API_KEY = None

# Constants
TARGET_CITIES = [
    # US Cities
    "Tampa, FL", "Memphis, TN", "Cleveland, OH",
    "Philadelphia, PA", "Las Vegas, NV", "Atlanta, GA",
    "Houston, TX", "Chicago, IL", "Dallas, TX", "Detroit, MI",
    # UK Cities
    "London, UK", "Manchester, UK", "Birmingham, UK",
    "Liverpool, UK", "Glasgow, UK", "Leeds, UK",
    "Sheffield, UK", "Bristol, UK", "Edinburgh, UK", "Leicester, UK"
]

FREE_PLATFORMS = ["weebly", "wix", "squarespace", "ecatholic"]

OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "leads.csv")

import time

def ensure_output_dir():
    """Ensure the output directory exists."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def search_churches(city):
    """
    Search for churches in a specific city using Google Places Text Search API.
    Handles pagination to fetch more results and filter out mega-churches.
    Returns a list of place_ids.
    """
    if not GOOGLE_PLACES_API_KEY:
        print("API Key is missing. Returning mock data for demonstration.")
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"churches in {city}",
        "key": GOOGLE_PLACES_API_KEY,
    }

    all_results = []

    try:
        while len(all_results) < CHURCH_LIMIT_PER_CITY:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            all_results.extend(results)

            next_page_token = data.get("next_page_token")
            if next_page_token and len(all_results) < CHURCH_LIMIT_PER_CITY:
                # API requires a short delay before next_page_token becomes valid
                time.sleep(2)
                params = {"pagetoken": next_page_token, "key": GOOGLE_PLACES_API_KEY}
            else:
                break

        # Return place_ids with their rating count to allow filtering later
        return [{"place_id": place["place_id"], "reviews": place.get("user_ratings_total", 0)} for place in all_results[:CHURCH_LIMIT_PER_CITY]]

    except requests.RequestException as e:
        print(f"Error searching for churches in {city}: {e}")
        return []

def get_church_details(place_id):
    """
    Get details for a specific church using Google Places Details API.
    Extracts name, address, phone, website URL, and Google Maps URL.
    """
    if not GOOGLE_PLACES_API_KEY:
        return None

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,url",
        "key": GOOGLE_PLACES_API_KEY,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        result = response.json().get("result", {})

        return {
            "name": result.get("name", "Unknown Name"),
            "address": result.get("formatted_address", "Unknown Address"),
            "phone": result.get("formatted_phone_number", "N/A"),
            "website": result.get("website", ""),
            "google_maps_url": result.get("url", ""),
            "email": "N/A" # Email will be extracted from website if possible
        }
    except requests.RequestException as e:
        print(f"Error fetching details for place_id {place_id}: {e}")
        return None

def extract_emails(html_content):
    """Attempt to extract email addresses from HTML content."""
    # Basic email regex
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, html_content)
    # Filter out common false positives like image extensions if needed, but basic regex works well enough for beginner level
    if emails:
        return emails[0]
    return "N/A"

def check_outdated_copyright(html_content):
    """Check if the copyright year on the website is before 2020."""
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text().lower()

    # Look for "copyright" or "©" followed by a year
    match = re.search(r'(?:copyright|©).*?(20\d{2})', text)
    if match:
        year = int(match.group(1))
        if year < 2020:
            return True
    return False

def evaluate_website(url):
    """
    Evaluate a website for status, free platform usage, and outdated copyright.
    Returns a dictionary of evaluation results.
    """
    if not url:
        return {
            "status": "NO WEBSITE",
            "is_broken": False,
            "is_free": False,
            "is_outdated": False,
            "email": "N/A"
        }

    evaluation = {
        "status": "ACTIVE",
        "is_broken": False,
        "is_free": False,
        "is_outdated": False,
        "email": "N/A"
    }

    # Check for free platform
    domain = urlparse(url).netloc.lower()
    for platform in FREE_PLATFORMS:
        if platform in domain:
            evaluation["is_free"] = True
            break

    try:
        # Timeout after 10 seconds to not hang indefinitely
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 404:
            evaluation["is_broken"] = True
            evaluation["status"] = "BROKEN (404)"
            return evaluation
        elif response.status_code >= 400:
            evaluation["is_broken"] = True
            evaluation["status"] = f"BROKEN ({response.status_code})"
            return evaluation

        html_content = response.text
        evaluation["email"] = extract_emails(html_content)
        evaluation["is_outdated"] = check_outdated_copyright(html_content)

    except requests.RequestException:
        # If connection fails completely, consider it broken
        evaluation["is_broken"] = True
        evaluation["status"] = "BROKEN (Connection Error)"

    return evaluation

def determine_priority(evaluation):
    """
    Determine lead priority based on website evaluation.
    - NO WEBSITE = "HOT LEAD"
    - BROKEN WEBSITE = "URGENT LEAD"
    - FREE PLATFORM = "UPGRADE LEAD"
    - OUTDATED (copyright before 2020) = "REDESIGN"
    """
    if evaluation["status"] == "NO WEBSITE":
        return "HOT LEAD"
    elif evaluation["is_broken"]:
        return "URGENT LEAD"
    elif evaluation["is_free"]:
        return "UPGRADE LEAD"
    elif evaluation["is_outdated"]:
        return "REDESIGN"
    return "NONE"

def generate_dm_message(church_name, priority):
    """
    Generate a personalized DM message based on the lead priority.
    Must mention faith2faith.us and behance.net/sabaali99.
    """
    base_intro = f"Hi {church_name} team! "
    portfolio_links = "You can see my recent project at faith2faith.us and my full portfolio at behance.net/sabaali99."

    if priority == "HOT LEAD":
        msg = f"{base_intro}I noticed you don't have a website yet. Having a strong online presence is crucial for reaching your community today. I specialize in building beautiful, affordable websites for churches. {portfolio_links} Let's connect!"
    elif priority == "URGENT LEAD":
        msg = f"{base_intro}I was trying to visit your website but noticed it's currently broken or returning an error. This can turn away potential visitors. I can help fix this quickly or build a reliable new site. {portfolio_links} Let's chat about getting you back online."
    elif priority == "UPGRADE LEAD":
        msg = f"{base_intro}I saw your current website and love what you're doing! However, using a free platform can sometimes limit your growth and professional look. I'd love to help you upgrade to a custom website that truly reflects your mission. {portfolio_links} Would you be open to a quick chat?"
    elif priority == "REDESIGN":
        msg = f"{base_intro}Your website has great information, but it looks like it might be a bit outdated. A modern redesign can significantly improve engagement with your congregation and visitors. {portfolio_links} I'd love to share some ideas with you!"
    else:
        msg = f"{base_intro}I love the work your church is doing. If you ever need help maintaining or upgrading your website to reach more people, I'm here to help. {portfolio_links} Blessings!"

    return msg

def main():
    ensure_output_dir()

    if not GOOGLE_PLACES_API_KEY:
        print("Warning: GOOGLE_PLACES_API_KEY is not set. The script will run but will likely fail API calls.")

    all_leads = []

    print(f"Starting church hunt in {len(TARGET_CITIES)} cities...")

    for city in TARGET_CITIES:
        print(f"\nSearching in {city}...")
        places = search_churches(city)

        if not places:
            print(f"No churches found in {city} or API error.")
            continue

        # Filter for "small" churches (e.g., fewer than 75 reviews) to hit our target demographic
        small_church_places = [p for p in places if p["reviews"] < 75]
        print(f"Found {len(places)} churches. After filtering out large churches, {len(small_church_places)} remain.")

        # Use tqdm for a progress bar
        for place in tqdm(small_church_places, desc=f"Evaluating {city}"):
            details = get_church_details(place["place_id"])
            if not details:
                continue

            # Evaluate website
            evaluation = evaluate_website(details["website"])

            # Update email if found on website
            if evaluation["email"] != "N/A":
                details["email"] = evaluation["email"]

            # Determine priority
            priority = determine_priority(evaluation)

            # Generate DM
            dm_message = generate_dm_message(details["name"], priority)

            # Parse city/state for the CSV
            city_name, state_name = map(str.strip, city.split(','))

            lead_data = {
                "Church Name": details["name"],
                "City": city_name,
                "State": state_name,
                "Phone": details["phone"],
                "Email": details["email"],
                "Website": details["website"] if details["website"] else "N/A",
                "Website Status": evaluation["status"],
                "Priority": priority,
                "Google Maps URL": details["google_maps_url"],
                "DM Message": dm_message
            }

            all_leads.append(lead_data)

    # Save to CSV using pandas
    if all_leads:
        df = pd.DataFrame(all_leads)

        # Sort leads to prioritize "HOT LEAD" (No Website) first, as that is the core target
        # Create a categorical data type with an explicit order
        priority_order = ["HOT LEAD", "URGENT LEAD", "UPGRADE LEAD", "REDESIGN", "NONE"]
        df["Priority"] = pd.Categorical(df["Priority"], categories=priority_order, ordered=True)

        # Sort by priority, then city
        df = df.sort_values(["Priority", "City"])

        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\nSuccess! Found {len(all_leads)} leads. Saved to {OUTPUT_FILE}")
    else:
        print("\nNo leads found.")

if __name__ == "__main__":
    main()

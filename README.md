# Church Hunter

An automated lead generation script that uses the Google Places API to find small churches in US cities and checks their website status to find opportunities for web development and marketing services.

## Features
- Searches for churches across 10 major US cities.
- Filters for small churches (under 500 Google reviews).
- Checks website status:
  - NO WEBSITE: Marked as HIGH priority.
  - BROKEN WEBSITE: Marked as URGENT priority.
  - FREE PLATFORM (e.g., Weebly, Wix, Squarespace): Marked as MEDIUM priority.
- Scrapes available emails and Facebook links from their websites.
- Outputs all findings to a CSV file (`churches_leads.csv`).

## Setup Instructions

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/yourusername/church-hunter.git
   cd church-hunter
   ```

2. **Install Python**
   Ensure you have Python 3 installed on your computer.

3. **Install Dependencies**
   Install the required Python packages using pip:
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your API Key**
   - Open `config.py`.
   - Replace `"YOUR_API_KEY_HERE"` with your actual Google Places API Key.
   - *Note: Keep your API key private. Do not commit `config.py` with your real key to a public repository.*

5. **Run the script**
   Execute the script from your terminal:
   ```bash
   python church_hunter.py
   ```

6. **View Results**
   Once the script finishes, open `churches_leads.csv` to view your ready-to-send outreach list.

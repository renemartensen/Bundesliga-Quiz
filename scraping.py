import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re

def fetch_with_retry(url, max_retries=3, delay_range=(1, 3)):
    """
    Fetch URL with retry logic and random delays to handle temporary failures
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limited
                print(f"  Rate limited (429), waiting longer...")
                time.sleep(random.uniform(5, 10))
            else:
                print(f"  HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            
        if attempt < max_retries - 1:
            delay = random.uniform(delay_range[0], delay_range[1])
            print(f"  Waiting {delay:.1f}s before retry...")
            time.sleep(delay)
    
    return None

class BundesligaScraper:

    def __init__(self, table_scraper, goalscorer_scraper, start_year=2005, end_year=2023):
        self.table_scraper = table_scraper
        self.goalscorer_scraper = goalscorer_scraper
        self.start_year = start_year
        self.end_year = end_year

    def scrape(self):
        all_data = {"seasons": []}
        
        for season in range(self.start_year, self.end_year + 1):
            standing_table = self.table_scraper.scrape(season)
            top_scorers = self.goalscorer_scraper.scrape(season)
            all_data["seasons"].append({
                "season": season,
                "standings": standing_table,
                "topscorers": top_scorers
            })

        with open("bundesliga_data.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print("✅ Data saved to bundesliga_data.json")


class Standings_Scraper:
    def parse_standings(self, table):
        standings = []
        rows = table.find_all("tr")

        # Header auslesen
        headers = [th.get("title") or th.get_text(strip=True) for th in rows[0].find_all("th")]

        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if not cols:
                continue

            entry = {}
            for i, col in enumerate(cols):
                if i < len(headers):
                    entry[headers[i]] = col
            standings.append(entry)

        return standings

    def scrape(self, season):
        season_end = season + 1
        season_str = f"{season}/{str(season_end)[-2:]}"
        url = f"https://de.wikipedia.org/wiki/Fu%C3%9Fball-Bundesliga_{season}/{str(season_end)[-2:]}"
        print(f"Scraping Standings {season_str} ... {url}")
        response = fetch_with_retry(url)
        if not response:
            print(f"❌ Failed to fetch {url} after all retries")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        tables = soup.find_all("table", {"class": "wikitable"})

        print("Found tables:", len(tables))
        standings = []
        if tables:
            standings = self.parse_standings(tables[0])

        return standings


class GoalscorerScraper:
    def is_topscorer_table(self, table):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        return any("Spieler" in h or "Name" in h for h in headers) \
            and any("Tore" in h for h in headers)

    def parse_topscorers(self, table):
        topscorers = []
        rows = table.find_all("tr")
        headers = ["Pl.", "Nat.", "Spieler", "Verein", "Tore"]

        rowspan_cache = {"Pl.": None, "Tore": None}
        row_span_index = 0
        row_span_start = 0
        last_pl = None

        print("Topscorer Table Headers:", headers)
        for row in rows[1:]:
            cols = []
            tds = row.find_all("td")
            ths = row.find_all("th")
            elements_in_row = ths + tds

            # Skip rows that do not contain data (in the end the table might have a note row)
            if len(elements_in_row) == 1:
                continue

            for i, td in enumerate(elements_in_row):

                # For the Tore column, remove any span (which might contain a hidden 0)
                if len(elements_in_row)-1 == i:
                    td.find('span').decompose() if td.find('span') else None

                # Handle row spans
                row_span = int(td.get("rowspan")) if td.get("rowspan") is not None else 0
                if row_span > 1:
                    row_span_index = row_span
                    row_span_start = row_span
                    if headers[i] == "Pl.":
                        rowspan_cache[headers[i]] = td.get_text(strip=True).lstrip("0")
                    else: 
                        rowspan_cache["Tore"] = td.get_text(strip=True).lstrip("0")

                # handle nationality and player name in one cell
                nationality = None
                value = None
                span = td.find('span')

                # Extract nationality from span
                if span and span.get_text(strip=True) != "0" and not span.get_text(strip=True).isdigit():
                    nationality = span.get_text(strip=True)

                aes = td.find_all('a')
                print("Aes:", [a.get_text(strip=True) for a in aes])
                print("TD:", td.get_text(strip=True))

                if len(aes) == 0:
                    value = td.get_text(strip=True)
                elif len(aes) == 1:
                    value = aes[0].get_text(strip=True)
                elif len(aes) == 2:
                    value = aes[1].get_text(strip=True)
                else: 
                    value = td.get_text(strip=True)

                if nationality:
                    cols.append(nationality)
                if value:
                    last_pl = value if headers[i] == "Pl." else last_pl
                    cols.append(value.lstrip("0"))
                
                # If the table format is such that "Pl." is missing in some rows, fill it with the last known value
                if headers[i] == "Pl." and not value:
                    cols.append(last_pl.lstrip("0"))

            # Handle row spans
            if row_span_index >= 1 and row_span_index < row_span_start:
                cols = [rowspan_cache["Pl."]] + cols
                cols.append(rowspan_cache["Tore"])
            row_span_index -= 1

            #print(cols)
            if not cols:
                continue

            entry = {}
            print("Cols:", cols)
            print("Headers:", headers)
            for i, col in enumerate(cols):
                if i < len(headers):
                    entry[headers[i]] = col
            topscorers.append(entry)
        return topscorers

    def scrape(self, season):
        season_end = season + 1
        season_str = f"{season}/{str(season_end)[-2:]}"
        url = f"https://de.wikipedia.org/wiki/Fu%C3%9Fball-Bundesliga_{season}/{str(season_end)[-2:]}"
        print(f"Scraping Topscorers {season_str} ... {url}")
        response = fetch_with_retry(url)
        if not response:
            print(f"❌ Failed to fetch {url} after all retries")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        tables = soup.find_all("table", {"class": "wikitable"})

        topscorer_table = [t for t in tables if self.is_topscorer_table(t)][0]
        topscorers = self.parse_topscorers(topscorer_table)

        return topscorers



if __name__ == "__main__":
    table_scraper = Standings_Scraper()
    goalscorer_scraper = GoalscorerScraper()
    scraper = BundesligaScraper(table_scraper, goalscorer_scraper, start_year=2005, end_year=2024)
    scraper.scrape()

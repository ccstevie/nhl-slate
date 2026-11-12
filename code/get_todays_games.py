import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import requests
import pandas as pd
from datetime import date, timedelta
from functools import reduce
import os
from shutil import which
from bs4 import BeautifulSoup
from io import StringIO

chromedriver_autoinstaller.install()

def _setup_chrome_options():
    """Set up standardized Chrome options for all Selenium operations."""
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    
    # Ensure Chrome binary is found to prevent hangs
    chrome_path = which("google-chrome") or which("google-chrome-stable")
    if chrome_path:
        options.binary_location = chrome_path
    
    return options


def get_games():
    url = "https://www.rotowire.com/hockey/nhl-lineups.php"

    options = _setup_chrome_options()
    driver = webdriver.Chrome(options=options)

    # Prevent infinite hangs
    driver.set_page_load_timeout(20)
    driver.set_script_timeout(20)

    try:
        driver.get(url)
    except Exception as e:
        print("ERROR: page load failed:", e)
        driver.quit()
        raise

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "lineups"))
        )
    except Exception:
        print("ERROR: lineup container never appeared")
        driver.quit()
        raise

    matchups = []
    lineups = driver.find_element(By.CLASS_NAME, "lineups") \
                    .find_elements(By.CLASS_NAME, "is-nhl")

    for lineup in lineups[:-1]:
        goalies = lineup.find_elements(By.CLASS_NAME, "lineup__player-highlight-name")
        away_goalie = goalies[0].text.strip().split()[-1]
        home_goalie = goalies[1].text.strip().split()[-1]
        teams = lineup.find_element(By.CLASS_NAME, 'lineup__teams').find_elements(By.TAG_NAME, 'a')
        teams = lineup.find_element(By.CLASS_NAME, 'lineup__matchup').find_elements(By.TAG_NAME, 'a')
        if len(teams) >= 2:
            away_team = teams[0].text.split(' (')[0]
            home_team = teams[1].text.split(' (')[0]
            matchups.append((away_team, home_team, away_goalie, home_goalie))

    driver.quit()
    return matchups

def get_goalie_gsax_ranks_last_20():
    url = "https://moneypuck.com/goalies.htm"

    options = _setup_chrome_options()
    driver = webdriver.Chrome(options=options)

    # Prevent infinite hangs
    driver.set_page_load_timeout(20)
    driver.set_script_timeout(20)

    try:
        driver.get(url)
    except Exception as e:
        print("ERROR: page load failed:", e)
        driver.quit()
        raise

    wait = WebDriverWait(driver, 10)

    try:
        # Wait for the dropdown
        dropdown = wait.until(EC.presence_of_element_located((By.ID, "num_games_type")))
        select = Select(dropdown)

        # Select "Last 20 Games"
        select.select_by_value("_20")

        # Wait for the table to update after selection
        wait.until(EC.presence_of_element_located((By.ID, "goaliesTable")))

        # Grab the table HTML
        table_html = driver.find_element(By.ID, "goaliesTable").get_attribute("outerHTML")
    except Exception as e:
        print("ERROR: failed to fetch goalie data:", e)
        driver.quit()
        raise
    finally:
        driver.quit()

    # Parse table manually
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")[1:]  # skip header

    data = []
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 7:  # ensure there are enough columns
            continue

        try:
            rank = int(tds[0].get_text(strip=True))
            goalie = tds[2].get_text(strip=True).split()[-1]
            gsa = float(tds[6].get_text(strip=True))
        except:
            continue

        data.append({"Rank": rank, "Goalie": goalie, "GSAx": gsa})

    # Convert to DataFrame and re-rank by GSAx
    df = pd.DataFrame(data)

    # Return as dictionary
    return dict(zip(df["Goalie"], df["Rank"]))

def load_or_fetch_goalie_ranks():
    cache_file = "goalie_gsax_20.csv"

    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
        return dict(zip(df["Goalie"], df["Rank"]))

    ranks = get_goalie_gsax_ranks_last_20()

    pd.DataFrame(
        [{"Goalie": k, "Rank": v} for k, v in ranks.items()]
    ).to_csv(cache_file, index=False)

    return ranks

def normalize_team(name):
    return (
        name.lower()
        .replace(".", "")
        .replace("é", "e")
        .replace(" ", "")
    )

# def get_team_streaks():
#     url = "https://www.nextteamup.com/nhl"
#     headers = {
#         "User-Agent": "Mozilla/5.0"  # avoid basic bot blocks
#     }

#     resp = requests.get(url, headers=headers, timeout=15)
#     resp.raise_for_status()

#     soup = BeautifulSoup(resp.text, "html.parser")

#     streaks = {}

#     # Grab all table rows (skip header automatically)
#     rows = soup.select("table tbody tr")

#     for row in rows:
#         tds = row.find_all("td")
#         if len(tds) < 3:
#             continue

#         team = tds[1].get_text(strip=True)
#         streak = tds[2].get_text(strip=True)

#         # Convert "+7" / "-3" → int
#         try:
#             streak = int(streak)
#         except ValueError:
#             continue

#         streaks[team] = streak

#     return streaks

def main():
    """Fetch hockey stats and write to CSV file."""
    today = date.today()
    start = today - timedelta(days=30)

    # Fetch team statistics from Natural Stat Trick
    key = os.environ.get("NST_API_KEY")

    if not key:
        raise ValueError(
            "NST_API_KEY is missing. Configure it in your local environment "
            "or GitHub Actions Secrets."
        )

    today = date.today()
    start = today - timedelta(days=30)

    url = "https://data.naturalstattrick.com/teamtable.php"

    params = {
        "fromseason": "20262027",
        "thruseason": "20262027",
        "stype": "2",
        "sit": "5v5",
        "score": "all",
        "rate": "y",
        "team": "all",
        "loc": "B",
        "gpf": "410",
        "fd": str(start),
        "td": str(today),
    }

    print(f"Fetching NST team stats from {start} to {today}...")

    response = requests.get(
        url,
        params=params,
        headers={"nst-key": key},
        timeout=30,
    )
    response.raise_for_status()

    html = response.text

    if "<table" not in html.lower():
        raise RuntimeError(
            "NST response did not contain an HTML table. "
            "Check the access key, endpoint, and response."
        )

    df = pd.read_html(
        StringIO(html),
        flavor="lxml",
        header=0,
        index_col=0,
        na_values=["-"],
    )[0]

    print("NST table loaded successfully:", df.shape)

    # Extract the statistics we want from NST
    columns = [
        "Team",
        "CF/60",
        "CA/60",
        "xGF/60",
        "xGA/60",
        "CF%",
        "GF%",
        "xGF%",
        "HDCF%",
        "SH%"
    ]

    final_df = df[columns].copy()

    # Prepare team statistics
    # NST's rate=y response provides the per-60 statistics directly.

    if "Team" not in df.columns:
        df = df.reset_index()

    rate_stats = ["CF/60", "CA/60", "xGF/60", "xGA/60"]
    percentage_stats = ["CF%", "GF%", "xGF%", "HDCF%", "SH%"]

    required_columns = ["Team"] + rate_stats + percentage_stats
    missing_columns = [
        col for col in required_columns if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing NST columns: {missing_columns}")

    # Keep the original values
    final_df = df[required_columns].copy()

    # Rank per-60 metrics
    # CA/60 and xGA/60: lower is better.
    lower_is_better = ["CA/60", "xGA/60"]

    for col in rate_stats:
        ascending = col in lower_is_better

        final_df[f"{col}_Rank"] = (
            pd.to_numeric(final_df[col], errors="coerce")
            .rank(method="min", ascending=ascending)
            .astype("Int64")
        )

    # Rank percentage metrics (higher is better)
    # Preserve the original naming convention:
    # CF% = rank, CF%_1 = actual percentage.

    for col in percentage_stats:
        final_df[f"{col}_1"] = final_df[col]

        final_df[col] = (
            pd.to_numeric(final_df[col], errors="coerce")
            .rank(method="min", ascending=False)
            .astype("Int64")
        )

    # Get matchups and goalie ranks
    matchups = get_games()
    goalie_ranks = load_or_fetch_goalie_ranks()

    # Build result dataframe with matchups and stats
    res = pd.DataFrame()
    for away, home, away_goalie, home_goalie in matchups:
        away_df = final_df[final_df["Team"].str.contains(away, case=False, na=False)]
        home_df = final_df[final_df["Team"].str.contains(home, case=False, na=False)]
        
        away_rank = goalie_ranks.get(away_goalie)
        home_rank = goalie_ranks.get(home_goalie)
        away_df = away_df.assign(
            Goalie=away_goalie,
            Goalie_Rank=away_rank
        )

        home_df = home_df.assign(
            Goalie=home_goalie,
            Goalie_Rank=home_rank
        )
        
        matchup_df = pd.concat([away_df, home_df], ignore_index=True)
        res = pd.concat([res, matchup_df], ignore_index=True)

    # Write results to CSV
    output_dir = os.path.join(os.path.dirname(__file__), "..", "public")
    output_file = os.path.join(output_dir, "result.csv")
    
    res.to_csv(output_file, index=False)

if __name__ == "__main__":
    main()

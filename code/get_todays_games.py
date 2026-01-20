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
        away_goalie = goalies[0].text.strip()
        home_goalie = goalies[1].text.strip()
        teams = lineup.find_element(By.CLASS_NAME, 'lineup__teams').find_elements(By.TAG_NAME, 'a')
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
        if len(tds) < 4:  # ensure there are enough columns
            continue

        try:
            rank = int(tds[0].get_text(strip=True))
            goalie = tds[2].get_text(strip=True)  # 3rd td is goalie name
            gsa = float(tds[3].get_text(strip=True))  # 4th td is GSAx
        except ValueError:
            continue

        data.append({"Rank": rank, "Goalie": goalie, "GSAx": gsa})

    # Convert to DataFrame and re-rank by GSAx
    df = pd.DataFrame(data)
    df = df.sort_values("GSAx", ascending=False).reset_index(drop=True)
    df["GSAx_Rank"] = df.index + 1

    # Return as dictionary
    return dict(zip(df["Goalie"], df["GSAx_Rank"]))

def load_or_fetch_goalie_ranks():
    cache_file = "goalie_gsax_20.csv"

    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
        return dict(zip(df["Goalie"], df["GSAx_Rank"]))

    ranks = get_goalie_gsax_ranks_last_20()

    pd.DataFrame(
        [{"Goalie": k, "GSAx_Rank": v} for k, v in ranks.items()]
    ).to_csv(cache_file, index=False)

    return ranks


def main():
    """Fetch hockey stats and write to CSV file."""
    today = date.today()
    start = today - timedelta(days=30)

    # Fetch team statistics from Natural Stat Trick
    url = f"https://www.naturalstattrick.com/teamtable.php?fromseason=20252026&thruseason=20252026&stype=2&sit=5v5&score=all&rate=n&team=all&loc=B&gpf=410&fd={start}&td={today}"
    req = requests.get(url, verify=False)
    df = pd.read_html(req.text, header=0, index_col=0, na_values=["-"])[0]

    # Create ranked dataframes for each stat
    cf = df.sort_values(by="CF%", ascending=False, ignore_index=True)
    cf.index += 1
    cf.reset_index(inplace=True)
    cf = cf.rename(columns={"index": "CF%"})
    cf = cf[["Team", "CF%"]]

    gf = df.sort_values(by="GF%", ascending=False, ignore_index=True)
    gf.index += 1
    gf.reset_index(inplace=True)
    gf = gf.rename(columns={"index": "GF%"})
    gf = gf[["Team", "GF%"]]

    xgf = df.sort_values(by="xGF%", ascending=False, ignore_index=True)
    xgf.index += 1
    xgf.reset_index(inplace=True)
    xgf = xgf.rename(columns={"index": "xGF%"})
    xgf = xgf[["Team", "xGF%"]]

    hdcf = df.sort_values(by="HDCF%", ascending=False, ignore_index=True)
    hdcf.index += 1
    hdcf.reset_index(inplace=True)
    hdcf = hdcf.rename(columns={"index": "HDCF%"})
    hdcf = hdcf[["Team", "HDCF%"]]

    sh = df.sort_values(by="SH%", ascending=False, ignore_index=True)
    sh.index += 1
    sh.reset_index(inplace=True)
    sh = sh.rename(columns={"index": "SH%"})
    sh = sh[["Team", "SH%"]]

    # Merge all stat dataframes
    dfs = [cf, gf, xgf, hdcf, sh]
    final_df = reduce(lambda left, right: pd.merge(left, right, on=['Team'], how='outer'), dfs)

    # Get matchups and goalie ranks
    matchups = get_games()
    goalie_ranks = load_or_fetch_goalie_ranks()

    # Build result dataframe with matchups and stats
    rows = []
    for i, (away, home, away_goalie, home_goalie) in enumerate(matchups):
        away_df = final_df[final_df["Team"].str.contains(away, case=False, na=False)]
        home_df = final_df[final_df["Team"].str.contains(home, case=False, na=False)]
        
        away_rank = goalie_ranks.get(away_goalie)
        home_rank = goalie_ranks.get(home_goalie)
        away_df = away_df.assign(Goalie=away_goalie, Goalie_GSAx_Rank=away_rank)
        home_df = home_df.assign(Goalie=home_goalie, Goalie_GSAx_Rank=home_rank)
        
        # Collect rows as dictionaries
        rows.extend(away_df.to_dict('records'))
        rows.extend(home_df.to_dict('records'))
        
        # Add blank row between matchups (but not after the last one)
        if i < len(matchups) - 1:
            blank_row = {col: None for col in rows[-1].keys()}
            rows.append(blank_row)

    # Create DataFrame once and write to CSV
    res = pd.DataFrame(rows)
    
    output_dir = os.path.join(os.path.dirname(__file__), "..", "public")
    output_file = os.path.join(output_dir, "result.csv")
    
    res.to_csv(output_file, index=False)

if __name__ == "__main__":
    main()

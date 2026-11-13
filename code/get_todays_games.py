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



def get_nhl_special_teams(season_id="20262027"):
    """
    Fetch NHL season-to-date team power-play, penalty-kill,
    and penalties-taken statistics.
    """

    base_url = "https://api.nhle.com/stats/rest/en/team"

    params = {
        "cayenneExp": f"seasonId={season_id} and gameTypeId=2",
        "limit": -1,
    }

    def fetch_report(report):
        response = requests.get(
            f"{base_url}/{report}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        rows = response.json().get("data", [])

        if len(rows) != 32:
            raise RuntimeError(
                f"Expected 32 teams from {report}, "
                f"received {len(rows)}."
            )

        print(f"NHL {report} report loaded: {len(rows)} teams")
        return pd.DataFrame(rows)

    # Fetch the three confirmed NHL API reports.
    pp_df = fetch_report("powerplay")
    pk_df = fetch_report("penaltykill")
    penalties_df = fetch_report("penalties")

    # Keep only the fields we need and normalize team names.
    pp_df = pp_df[["teamFullName", "powerPlayPct"]].copy()
    pp_df["Team_Normalized"] = pp_df["teamFullName"].apply(normalize_team)
    pp_df["PP%_1"] = pd.to_numeric(
        pp_df["powerPlayPct"], errors="coerce"
    ) * 100
    pp_df = pp_df[["Team_Normalized", "PP%_1"]]

    pk_df = pk_df[["teamFullName", "penaltyKillPct"]].copy()
    pk_df["Team_Normalized"] = pk_df["teamFullName"].apply(normalize_team)
    pk_df["PK%_1"] = pd.to_numeric(
        pk_df["penaltyKillPct"], errors="coerce"
    ) * 100
    pk_df = pk_df[["Team_Normalized", "PK%_1"]]

    penalties_df = penalties_df[
        ["teamFullName", "penalties", "gamesPlayed"]
    ].copy()
    penalties_df["Team_Normalized"] = (
        penalties_df["teamFullName"].apply(normalize_team)
    )

    penalties_df["Penalties_Per_Game"] = (
        pd.to_numeric(penalties_df["penalties"], errors="coerce")
        / pd.to_numeric(penalties_df["gamesPlayed"], errors="coerce")
    )

    penalties_df = penalties_df[
        ["Team_Normalized", "Penalties_Per_Game"]
    ]

    # Combine all three reports by team.
    result = pp_df.merge(
        pk_df,
        on="Team_Normalized",
        how="inner",
        validate="one_to_one",
    )

    result = result.merge(
        penalties_df,
        on="Team_Normalized",
        how="inner",
        validate="one_to_one",
    )

    # Validate the returned data.
    metric_columns = [
        "PP%_1",
        "PK%_1",
        "Penalties_Per_Game",
    ]

    if len(result) != 32 or result[metric_columns].isna().any().any():
        raise RuntimeError(
            "Special-teams data is incomplete. "
            f"Received {len(result)} teams."
        )

    # Rank special-teams metrics.
    # Higher PP% and PK% are better.
    result["PP%_Rank"] = (
        result["PP%_1"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    result["PK%_Rank"] = (
        result["PK%_1"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    # Fewer penalties per game is better.
    result["Penalties_Per_Game_Rank"] = (
        result["Penalties_Per_Game"]
        .rank(method="min", ascending=True)
        .astype("Int64")
    )

    return result

    """
    Fetch NHL season-to-date team power-play, penalty-kill,
    and penalties-taken statistics.

    season_id example: 20262027
    """

    base_url = "https://api.nhle.com/stats/rest/en/team"

    params = {
        "cayenneExp": (
            f"seasonId={season_id} and gameTypeId=2"
        ),
        "limit": -1,
    }

    def fetch_report(report):
        response = requests.get(
            f"{base_url}/{report}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        rows = payload.get("data", [])

        if not rows:
            raise RuntimeError(
                f"NHL API returned no data for {report}. "
                f"Response: {payload}"
            )

        print(f"NHL {report} report loaded: {len(rows)} teams")
        return rows

    # The summary report contains both PP% and PK%.
    summary_rows = fetch_report("summary")

    # The penalties report contains team penalty totals.
    penalty_rows = fetch_report("penalties")

    def get_team_name(row):
        for field in [
            "franchiseName",
            "teamFullName",
            "teamName",
            "team",
        ]:
            if row.get(field):
                return row[field]

        raise KeyError(
            f"Could not identify team name. Available fields: "
            f"{list(row.keys())}"
        )

    def get_field(row, candidates):
        for field in candidates:
            value = row.get(field)
            if value is not None:
                return float(value)

        raise KeyError(
            f"Could not find any of {candidates}. "
            f"Available fields: {list(row.keys())}"
        )

    # Build a lookup of power-play and penalty-kill statistics.
    special_teams = {}

    for row in summary_rows:
        team = normalize_team(get_team_name(row))

        pp_pct = get_field(
            row,
            ["powerPlayPct", "powerPlayPercentage", "ppPct"],
        )

        pk_pct = get_field(
            row,
            ["penaltyKillPct", "penaltyKillPercentage", "pkPct"],
        )

        # NHL API percentages are generally decimals (e.g. 0.23).
        # Convert to the 0-100 scale used by our React frontend.
        if pp_pct <= 1:
            pp_pct *= 100

        if pk_pct <= 1:
            pk_pct *= 100

        special_teams[team] = {
            "PP%_1": pp_pct,
            "PK%_1": pk_pct,
        }

    # Add penalties taken per game.
    for row in penalty_rows:
        team = normalize_team(get_team_name(row))

        penalties_per_game = row.get("penaltiesPerGame")

        if penalties_per_game is None:
            total_penalties = get_field(
                row,
                ["penalties", "totalPenalties"],
            )

            games_played = get_field(
                row,
                ["gamesPlayed"],
            )

            penalties_per_game = (
                total_penalties / games_played
                if games_played > 0 else None
            )

        if team in special_teams:
            special_teams[team]["Penalties_Per_Game"] = (
                penalties_per_game
            )

    records = []

    for team, stats in special_teams.items():
        records.append({
            "Team_Normalized": team,
            **stats,
        })

    result = pd.DataFrame(records)

    # Validate that we received all three metrics.
    required = [
        "PP%_1",
        "PK%_1",
        "Penalties_Per_Game",
    ]

    missing = [
        col for col in required
        if col not in result.columns or result[col].isna().any()
    ]

    if missing:
        raise RuntimeError(
            f"Missing special-teams statistics: {missing}. "
            "Check the NHL API response fields."
        )

    if len(result) != 32:
        raise RuntimeError(
            f"Expected 32 NHL teams, received {len(result)}."
        )

    # Rank percentages: higher is better.
    result["PP%_Rank"] = (
        result["PP%_1"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    result["PK%_Rank"] = (
        result["PK%_1"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    # Rank penalties: fewer penalties is better.
    result["Penalties_Per_Game_Rank"] = (
        result["Penalties_Per_Game"]
        .rank(method="min", ascending=True)
        .astype("Int64")
    )

    return result

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

    # Fetch and merge NHL season-to-date special-teams stats.
    special_teams = get_nhl_special_teams("20262027")

    final_df["Team_Normalized"] = (
        final_df["Team"].apply(normalize_team)
    )

    final_df = final_df.merge(
        special_teams,
        on="Team_Normalized",
        how="left",
        validate="one_to_one",
    )

    final_df.drop(columns=["Team_Normalized"], inplace=True)

    # Make sure every NST team received special-teams data.
    special_teams_columns = [
        "PP%_1",
        "PP%_Rank",
        "PK%_1",
        "PK%_Rank",
        "Penalties_Per_Game",
        "Penalties_Per_Game_Rank",
    ]

    if final_df[special_teams_columns].isna().any().any():
        missing_teams = final_df[
            final_df[special_teams_columns].isna().any(axis=1)
        ]["Team"].tolist()

        raise RuntimeError(
            f"Missing special-teams data for: {missing_teams}"
        )

    print("Special-teams statistics merged successfully.")

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

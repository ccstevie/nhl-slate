
import json
import os
import re
from datetime import datetime, timezone

import pandas as pd
from google import genai
from google.genai import types
import time
from google.genai.errors import ServerError

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "..", "public")

CONTEXT_FILE = os.path.join(PUBLIC_DIR, "game_previews.json")
STATS_FILE = os.path.join(PUBLIC_DIR, "result.csv")
OUTPUT_FILE = os.path.join(PUBLIC_DIR, "ai_previews.json")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.environ.get(
    "GEMINI_FALLBACK_MODEL",
    "gemini-3.5-flash-lite"
)

# Actual metric column, rank column, display label, unit
METRICS = {
    "corsi_for_pct": (
        "CF%_1", "CF%", "Corsi For %", "%"
    ),
    "goals_for_pct": (
        "GF%_1", "GF%", "Goals For %", "%"
    ),
    "expected_goals_pct": (
        "xGF%_1", "xGF%", "Expected Goals %", "%"
    ),
    "high_danger_chances_pct": (
        "HDCF%_1", "HDCF%", "High Danger Chances %", "%"
    ),
    "shooting_pct": (
        "SH%_1", "SH%", "Shooting %", "%"
    ),
    "corsi_for_per60": (
        "CF/60", "CF/60_Rank", "Corsi For / 60", "per 60"
    ),
    "corsi_against_per60": (
        "CA/60", "CA/60_Rank", "Corsi Against / 60", "per 60"
    ),
    "expected_goals_for_per60": (
        "xGF/60", "xGF/60_Rank", "Expected Goals For / 60", "per 60"
    ),
    "expected_goals_against_per60": (
        "xGA/60", "xGA/60_Rank", "Expected Goals Against / 60", "per 60"
    ),
    "power_play_pct": (
        "PP%_1", "PP%_Rank", "Power Play %", "%"
    ),
    "penalty_kill_pct": (
        "PK%_1", "PK%_Rank", "Penalty Kill %", "%"
    ),
    "penalties_taken_per60": (
        "Penalties_Taken_Per60",
        "Penalties_Taken_Per60_Rank",
        "Penalties Taken / 60",
        "per 60"
    ),
}


# --------------------------------------------------
# Data preparation
# --------------------------------------------------

def normalize_team(name):
    return (
        str(name)
        .lower()
        .replace(".", "")
        .replace("é", "e")
        .replace(" ", "")
    )


def find_team_stats(team_name, stats_df):
    """
    Find the team's row in result.csv.

    The matchup data uses shortened names such as Rangers,
    while the CSV may contain New York Rangers or NY Rangers.
    """

    target = normalize_team(team_name)

    matches = stats_df[
        stats_df["Team"].apply(
            lambda name: target in normalize_team(name)
        )
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one stats row for {team_name}, "
            f"found {len(matches)}. "
            f"Matches: {matches['Team'].tolist()}"
        )

    row = matches.iloc[0]

    team_stats = {}

    for key, (value_col, rank_col, label, unit) in METRICS.items():
        value = pd.to_numeric(
            pd.Series([row.get(value_col)]),
            errors="coerce"
        ).iloc[0]

        rank = pd.to_numeric(
            pd.Series([row.get(rank_col)]),
            errors="coerce"
        ).iloc[0]

        team_stats[key] = {
            "label": label,
            "value": None if pd.isna(value) else round(float(value), 2),
            "unit": unit,
            "league_rank": None if pd.isna(rank) else int(rank),
        }

    return team_stats


def find_goalie_info(team_name, goalie_name, stats_df):
    """
    Retrieve the goalie and their GSAx ranking from result.csv.
    Lower rank is better.
    """

    target = normalize_team(team_name)

    team_rows = stats_df[
        stats_df["Team"].apply(
            lambda name: target in normalize_team(name)
        )
    ]

    if len(team_rows) != 1:
        raise RuntimeError(
            f"Expected one team row for {team_name}, "
            f"found {len(team_rows)}."
        )

    row = team_rows.iloc[0]

    rank = pd.to_numeric(
        pd.Series([row.get("Goalie_Rank")]),
        errors="coerce"
    ).iloc[0]

    return {
        "name": goalie_name,
        "gsax_rank_last_20": (
            None if pd.isna(rank) else int(rank)
        ),
    }


def build_game_input(game, stats_df):
    away = game["away_team"]
    home = game["home_team"]

    return {
        "game_date": game["game_date"],
        "away_team": {
            "name": away["team"],
            "abbreviation": away["team_abbrev"],
            "recent_context": {
                "current_streak": away["current_streak"],
                "games_last_4_days": away["games_last_4_days"],
                "games_last_7_days": away["games_last_7_days"],
                "rest_days": away["rest_days"],
                "previous_head_to_head": away["previous_head_to_head"],
            },
            "statistics": find_team_stats(away["team"], stats_df),
            "goalie": find_goalie_info(
                away["team"],
                game.get("goalies", {}).get("away"),
                stats_df
            ),
        },
        "home_team": {
            "name": home["team"],
            "abbreviation": home["team_abbrev"],
            "recent_context": {
                "current_streak": home["current_streak"],
                "games_last_4_days": home["games_last_4_days"],
                "games_last_7_days": home["games_last_7_days"],
                "rest_days": home["rest_days"],
                "previous_head_to_head": home["previous_head_to_head"],
            },
            "statistics": find_team_stats(home["team"], stats_df),
            "goalie": find_goalie_info(
                home["team"],
                game.get("goalies", {}).get("home"),
                stats_df
            ),
        }
    }


# --------------------------------------------------
# AI generation
# --------------------------------------------------

PREVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string"
        },
        "summary": {
            "type": "string"
        },
        "away_analysis": {
            "type": "string"
        },
        "home_analysis": {
            "type": "string"
        },
        "matchup_edges": {
            "type": "array",
            "items": {"type": "string"}
        },
        "x_factor": {
            "type": "string"
        },
        "key_question": {
            "type": "string"
        }
    },
    "required": [
        "headline",
        "summary",
        "away_analysis",
        "home_analysis",
        "matchup_edges",
        "x_factor",
        "key_question"
    ],
    "additionalProperties": False
}


SYSTEM_PROMPT = """
You are an experienced NHL analyst writing original, insightful
game previews for a hockey analytics dashboard.

You will receive structured information about two NHL teams.
This includes recent results, streaks, rest, schedule density,
head-to-head results, goalie names, and team statistics.

Your job is to interpret the information and explain what it
means for the upcoming matchup.

ANALYTICAL GUIDELINES:

1. Compare the two teams directly. Do not just list their stats.

2. Use Corsi For % to discuss possession and shot-attempt control.

3. Compare Goals For % with Expected Goals %.
   - A higher Goals For % than Expected Goals % can indicate
     that results have exceeded underlying expected-goal share.
   - A lower Goals For % can indicate that results have lagged
     behind underlying expected-goal share.
   - Do not automatically call this luck or assume regression
     is guaranteed.

4. Use Expected Goals For / 60 and Expected Goals Against / 60
   to discuss offensive and defensive chance generation.

5. Use High Danger Chances % to discuss dangerous scoring chances.

6. Consider Shooting % alongside expected-goal performance.
   A high shooting percentage alone does not prove a team is
   playing well or will continue scoring at that rate.

7. Evaluate power play, penalty kill, and penalties taken together.

8. Consider winning/losing streaks, recent workload, and rest.
   Do not confuse full rest days with total days since the
   previous game.

9. League ranks use 1 as best. Interpret each metric in the
   correct direction:
   - Higher is generally better: CF%, GF%, xGF%, HDCF%,
     CF/60, xGF/60, PP%, PK%.
   - Lower is generally better: CA/60, xGA/60,
     penalties taken per 60.
   - Shooting percentage is context-dependent.

10. Acknowledge when the data does not support a strong
    conclusion. Never invent injuries, news, goalie confirmation,
    quotes, or facts not included in the supplied information.

11. Do not make betting recommendations or claim certainty
    about the winner.

12. Evaluate the starting/projected goalies when goalie information
    is available.
    - Goalie GSAx rank is based on the last 20 games.
    - Rank 1 is best.
    - A lower rank indicates stronger recent GSAx performance.
    - Compare the two goalies when both rankings are available.
    - Do not assume that a goalie is confirmed to start.
    - Do not treat a missing ranking as poor performance.
    - Do not overstate small differences in goalie rankings.

WRITING STYLE:

- Sound like a knowledgeable hockey analyst, not a statistics
  textbook.
- Be specific and use actual numbers when they strengthen
  the analysis.
- Avoid mentioning every metric just because it is available.
- Explain why a statistical difference matters.
- Identify interesting contradictions between results and
  underlying performance.
- Keep the preview readable and relatively concise.
- Write original analysis rather than generic commentary.
"""



def generate_preview(client, game_input):

    prompt = (
        "Write an NHL game preview using the following "
        "data. Treat the supplied data as the source "
        "of truth.\n\n"
        + json.dumps(game_input, indent=2)
    )

    models_to_try = [MODEL, FALLBACK_MODEL]

    for model in models_to_try:

        for attempt in range(3):

            try:
                print(
                    f"Trying {model} "
                    f"(attempt {attempt + 1}/3)"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_json_schema=PREVIEW_SCHEMA,
                        temperature=0.7,
                        max_output_tokens=2000,
                    ),
                )

                if not response.text:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                print(f"Successfully generated using {model}")

                return json.loads(response.text)

            except ServerError as error:

                if error.code != 503:
                    raise

                if attempt < 2:
                    wait_seconds = 10 * (2 ** attempt)

                    print(
                        f"{model} is overloaded. "
                        f"Retrying in {wait_seconds} seconds..."
                    )

                    time.sleep(wait_seconds)

                else:
                    print(
                        f"{model} failed after 3 attempts."
                    )

    raise RuntimeError(
        "Both Gemini models failed after all retry attempts."
    )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    client = genai.Client(api_key=api_key)

    with open(CONTEXT_FILE, "r", encoding="utf-8") as file:
        game_contexts = json.load(file)

    stats_df = pd.read_csv(STATS_FILE)

    previews = []

    for game in game_contexts["games"]:
        away = game["away_team"]["team"]
        home = game["home_team"]["team"]

        print(f"Generating AI preview: {away} @ {home}")

        game_input = build_game_input(game, stats_df)
        ai_preview = generate_preview(client, game_input)

        previews.append({
            "game_date": game["game_date"],
            "away_team": away,
            "home_team": home,
            "goalies": game.get("goalies", {}),
            "preview": ai_preview,
        })

        print(f"Preview generated: {away} @ {home}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "games": previews,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print(f"AI previews saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

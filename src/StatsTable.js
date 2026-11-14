
// src/StatsTable.js
import React, { useEffect, useState } from 'react';
import Papa from 'papaparse';
import './StatsTable.css';

const metricGroups = [
  {
    title: 'Corsi',
    summaryMetrics: [
      {
        label: 'Corsi For %',
        value: 'CF%_1',
        rank: 'CF%',
        percent: true,
      },
    ],
    detailMetrics: [
      {
        label: 'Corsi For / 60',
        value: 'CF/60',
        rank: 'CF/60_Rank',
      },
      {
        label: 'Corsi Against / 60',
        value: 'CA/60',
        rank: 'CA/60_Rank',
      },
    ],
  },
  {
    title: 'Expected Goals & Results',
    summaryMetrics: [
      {
        label: 'Expected Goals For %',
        value: 'xGF%_1',
        rank: 'xGF%',
        percent: true,
      },
      {
        label: 'Goals For %',
        value: 'GF%_1',
        rank: 'GF%',
        percent: true,
      },
    ],
    detailMetrics: [
      {
        label: 'Expected Goals For / 60',
        value: 'xGF/60',
        rank: 'xGF/60_Rank',
      },
      {
        label: 'Expected Goals Against / 60',
        value: 'xGA/60',
        rank: 'xGA/60_Rank',
      },
    ],
  },
  {
    title: 'Chance Quality & Finishing',
    summaryMetrics: [
      {
        label: 'High Danger Chances For %',
        value: 'HDCF%_1',
        rank: 'HDCF%',
        percent: true,
      },
      {
        label: 'Shooting %',
        value: 'SH%_1',
        rank: 'SH%',
        percent: true,
      },
    ],
    detailMetrics: [],
  },
  {
    title: 'Special Teams & Discipline',
    summaryMetrics: [],
    detailMetrics: [
      {
        label: 'Power Play %',
        value: 'PP%_1',
        rank: 'PP%_Rank',
        percent: true,
      },
      {
        label: 'Penalty Kill %',
        value: 'PK%_1',
        rank: 'PK%_Rank',
        percent: true,
      },
      {
        label: 'Penalties Taken / 60',
        value: 'Penalties_Taken_Per60',
        rank: 'Penalties_Taken_Per60_Rank',
      },
    ],
  },
];

const teamAbbreviations = {
  "Anaheim Ducks": "ANA",
  "Boston Bruins": "BOS",
  "Buffalo Sabres": "BUF",
  "Calgary Flames": "CGY",
  "Carolina Hurricanes": "CAR",
  "Chicago Blackhawks": "CHI",
  "Colorado Avalanche": "COL",
  "Columbus Blue Jackets": "CBJ",
  "Dallas Stars": "DAL",
  "Detroit Red Wings": "DET",
  "Edmonton Oilers": "EDM",
  "Florida Panthers": "FLA",
  "Los Angeles Kings": "LAK",
  "Minnesota Wild": "MIN",
  "Montreal Canadiens": "MTL",
  "Nashville Predators": "NSH",
  "New Jersey Devils": "NJD",
  "New York Islanders": "NYI",
  "New York Rangers": "NYR",
  "Ottawa Senators": "OTT",
  "Philadelphia Flyers": "PHI",
  "Pittsburgh Penguins": "PIT",
  "San Jose Sharks": "SJS",
  "Seattle Kraken": "SEA",
  "St. Louis Blues": "STL",
  "Tampa Bay Lightning": "TBL",
  "Toronto Maple Leafs": "TOR",
  "Utah Mammoth": "UTA",
  "Vancouver Canucks": "VAN",
  "Vegas Golden Knights": "VGK",
  "Washington Capitals": "WSH",
  "Winnipeg Jets": "WPG",
};

function TeamLogo({ team }) {
  const abbreviation = teamAbbreviations[team];

  if (!abbreviation) return null;

  return (
    <img
      className="team-logo"
      src={`https://assets.nhle.com/logos/nhl/svg/${abbreviation}_dark.svg`}
      alt={`${team} logo`}
      onError={(e) => {
        e.currentTarget.style.display = 'none';
      }}
    />
  );
}

function getRank(team, column) {
  const value = Number(team[column]);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function getAdvantage(away, home, rankColumn) {
  const awayRank = getRank(away, rankColumn);
  const homeRank = getRank(home, rankColumn);

  if (awayRank === null || homeRank === null) {
    return ['neutral', 'neutral'];
  }

  if (awayRank < homeRank) {
    return ['better', 'worse'];
  }

  if (homeRank < awayRank) {
    return ['worse', 'better'];
  }

  return ['neutral', 'neutral'];
}

function formatValue(value, isPercent) {
  const number = Number(value);

  if (!Number.isFinite(number)) return 'N/A';

  return isPercent
    ? `${number.toFixed(2)}%`
    : number.toFixed(2);
}

function normalizeTeamName(name) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function findAiPreview(awayTeam, homeTeam, previews) {
  const normalize = normalizeTeamName;

  return previews.find((game) => {
    const gameAway = normalize(game.away_team);
    const gameHome = normalize(game.home_team);
    const away = normalize(awayTeam);
    const home = normalize(homeTeam);

    return (
      gameAway &&
      gameHome &&
      away.includes(gameAway) &&
      home.includes(gameHome)
    );
  });
}

function TeamStat({ team, metric, status }) {
  const rank = getRank(team, metric.rank);

  return (
    <div className={`comparison-value ${status}`}>
      <strong>
        {rank !== null ? `#${rank}` : 'N/A'}
      </strong>
      <span>
        {formatValue(team[metric.value], metric.percent)}
      </span>
    </div>
  );
}

function StatsTable() {
  const [data, setData] = useState([]);
  const [expandedRows, setExpandedRows] = useState({});
  const [expandedGroups, setExpandedGroups] = useState({});
  const [aiPreviews, setAiPreviews] = useState([]);
  const [selectedPreview, setSelectedPreview] = useState(null);

  useEffect(() => {
    fetch('/result.csv')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Could not load result.csv');
        }
        return response.text();
      })
      .then((text) => {
        const parsed = Papa.parse(text, {
          header: true,
          skipEmptyLines: true,
        });

        setData(parsed.data.filter((row) => row.Team));
      })
      .catch((error) => {
        console.error('Error loading hockey stats:', error);
      });
  }, []);

  useEffect(() => {
    fetch('/ai_previews.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Could not load ai_previews.json');
        }
        return response.json();
      })
      .then((json) => {
        setAiPreviews(json.games || []);
      })
      .catch((error) => {
        console.error('Error loading AI previews:', error);
      });
  }, []);

  // CSV rows are ordered away team, then home team.
  const matchups = [];

  for (let i = 0; i + 1 < data.length; i += 2) {
    matchups.push({
      away: data[i],
      home: data[i + 1],
      id: i,
    });
  }

  const toggleRow = (id) => {
    setExpandedRows((previous) => ({
      ...previous,
      [id]: !previous[id],
    }));
  };

  const toggleGroup = (rowId, groupTitle) => {
    const key = `${rowId}-${groupTitle}`;

    setExpandedGroups((previous) => ({
      ...previous,
      [key]: !previous[key],
    }));
  };

  if (data.length === 0) {
    return (
      <div className="stats-container">
        <h2>Today's Matchups</h2>
        <p className="loading-message">Loading matchups...</p>
      </div>
    );
  }

  return (
    <div className="stats-container">
      <header className="dashboard-header">
        <div className="brand">
          <span className="brand-icon">◆</span>
          <span>ICE ANALYTICS</span>
        </div>
        <span className="season-label">NHL TEAM ANALYTICS</span>
      </header>

      <div className="page-heading">
        <h2>Today's Matchups</h2>
        <p>Advanced team statistics and head-to-head comparisons</p>
      </div>

      <div className="matchup-list">
        {matchups.map(({ away, home, id }) => {
          const isExpanded = !!expandedRows[id];

          const aiPreview = findAiPreview(
            away.Team,
            home.Team,
            aiPreviews
          );

          const [awayGoalieStatus, homeGoalieStatus] =
            getAdvantage(away, home, 'Goalie_Rank');

          return (
            <section className="matchup-card" key={id}>
              <div className="matchup-summary">
                <div className="team-summary away-team">
                  <span className="team-side">AWAY</span>
                  <div className="team-name-row">
                    <TeamLogo team={away.Team} />
                    <h3>{away.Team}</h3>
                  </div>
                  <span className="goalie">
                    Goalie: {away.Goalie || 'Unknown'}
                  </span>
                  <span className={`goalie-rank ${awayGoalieStatus}`}>
                    Goalie rank: {getRank(away, 'Goalie_Rank') !== null
                      ? `#${getRank(away, 'Goalie_Rank')}`
                      : 'N/A'}
                  </span>
                </div>

                <div className="matchup-middle">
                  <div className="versus">VS</div>

                  <div className="matchup-actions">
                    <button
                      className="details-button"
                      onClick={() => toggleExpanded(id)}
                    >
                      {isExpanded ? 'Hide Stats' : 'Compare Stats'}
                    </button>

                    <button
                      className="ai-icon-button"
                      onClick={() => setSelectedPreview(aiPreview)}
                      disabled={!aiPreview}
                      aria-label="AI Game Preview"
                      title="AI Game Preview"
                    >
                      ✦
                    </button>
                  </div>
                </div>

                <div className="team-summary home-team">
                  <span className="team-side">HOME</span>
                  <div className="team-name-row">
                    <TeamLogo team={home.Team} />
                    <h3>{home.Team}</h3>
                  </div>
                  <span className="goalie">
                    Goalie: {home.Goalie || 'Unknown'}
                  </span>
                  <span className={`goalie-rank ${homeGoalieStatus}`}>
                    Goalie rank: {getRank(home, 'Goalie_Rank') !== null
                      ? `#${getRank(home, 'Goalie_Rank')}`
                      : 'N/A'}
                  </span>
                </div>

              </div>

              {isExpanded && (
                <div className="comparison-panel">
                  <div className="comparison-heading">
                    <h4>Head-to-Head Comparison</h4>
                    <span>
                      Lower ranking number = better league ranking
                    </span>
                  </div>

                  <div className="comparison-column-headings">
                    <span>{away.Team}</span>
                    <span>STATISTIC</span>
                    <span>{home.Team}</span>
                  </div>

                  <div className="comparison-table">
                    {metricGroups.map((group) => {
                      const groupKey = `${id}-${group.title}`;
                      const isGroupExpanded = !!expandedGroups[groupKey];

                      const allMetrics = [
                        ...group.summaryMetrics,
                        ...(isGroupExpanded ? group.detailMetrics : []),
                      ];

                      return (
                        <div className="metric-group" key={group.title}>

                          <div
                            className={`metric-group-heading ${
                              group.detailMetrics.length > 0 ? 'clickable' : ''
                            }`}
                            onClick={() => {
                              if (group.detailMetrics.length > 0) {
                                toggleGroup(id, group.title);
                              }
                            }}
                            role={group.detailMetrics.length > 0 ? 'button' : undefined}
                            tabIndex={group.detailMetrics.length > 0 ? 0 : undefined}
                            onKeyDown={(e) => {
                              if (
                                group.detailMetrics.length > 0 &&
                                (e.key === 'Enter' || e.key === ' ')
                              ) {
                                e.preventDefault();
                                toggleGroup(id, group.title);
                              }
                            }}
                          >
                            <span>{group.title}</span>

                            {group.detailMetrics.length > 0 && (
                              <span className="group-toggle">
                                {isGroupExpanded ? '−' : '+'}
                              </span>
                            )}
                          </div>

                          {allMetrics.map((metric) => {
                            const [awayStatus, homeStatus] =
                              getAdvantage(away, home, metric.rank);

                            return (
                              <div
                                className="comparison-row"
                                key={metric.value}
                              >
                                <TeamStat
                                  team={away}
                                  metric={metric}
                                  status={awayStatus}
                                />

                                <div className="metric-label">
                                  {metric.label}
                                </div>

                                <TeamStat
                                  team={home}
                                  metric={metric}
                                  status={homeStatus}
                                />
                              </div>
                            );
                          })}

                        </div>
                      );
                    })}
                  </div>

                  <div className="comparison-legend">
                    <span><i className="legend-dot better-dot" /> Better</span>
                    <span><i className="legend-dot worse-dot" /> Worse</span>
                    <span><i className="legend-dot neutral-dot" /> Tied / N/A</span>
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>

      {selectedPreview && (
        <div
          className="ai-modal-overlay"
          onClick={() => setSelectedPreview(null)}
        >
          <div
            className="ai-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-preview-title"
          >
            <div className="ai-modal-header">
              <div>
                <span className="ai-modal-label">
                  ✦ AI GAME ANALYSIS
                </span>
                <h2 id="ai-preview-title">
                  {selectedPreview.preview.headline}
                </h2>
                <p>
                  {selectedPreview.away_team} @ {selectedPreview.home_team}
                </p>
              </div>

              <button
                className="ai-modal-close"
                onClick={() => setSelectedPreview(null)}
                aria-label="Close preview"
              >
                ×
              </button>
            </div>

            <div className="ai-modal-body">
              <section className="quick-takeaway">
                <h3>
                  <span>✦</span> THE QUICK TAKEAWAY
                </h3>
                <p>
                  {selectedPreview.preview.quick_takeaway ||
                    selectedPreview.preview.summary}
                </p>
              </section>

              <section className="ai-preview-section">
                <h3>Game Summary</h3>
                <p>{selectedPreview.preview.summary}</p>
              </section>

              <div className="ai-team-analysis">
                <section className="ai-preview-section">
                  <h3>{selectedPreview.away_team}</h3>
                  <p>{selectedPreview.preview.away_analysis}</p>
                </section>

                <section className="ai-preview-section">
                  <h3>{selectedPreview.home_team}</h3>
                  <p>{selectedPreview.preview.home_analysis}</p>
                </section>
              </div>

              <section className="ai-preview-section">
                <h3>Key Matchup Edges</h3>
                <ul className="matchup-edges">
                  {selectedPreview.preview.matchup_edges?.map(
                    (edge, index) => (
                      <li key={index}>{edge}</li>
                    )
                  )}
                </ul>
              </section>

              <div className="ai-insight-grid">
                <section className="ai-insight">
                  <h3>X-Factor</h3>
                  <p>{selectedPreview.preview.x_factor}</p>
                </section>

                <section className="ai-insight">
                  <h3>Key Question</h3>
                  <p>{selectedPreview.preview.key_question}</p>
                </section>
              </div>
            </div>

            <div className="ai-modal-footer">
              <span>
                AI-generated analysis based on available team statistics
                and game context.
              </span>
              <button
                onClick={() => setSelectedPreview(null)}
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StatsTable;


// src/StatsTable.js
import React, { useEffect, useState } from 'react';
import Papa from 'papaparse';
import './StatsTable.css';

const metrics = [
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
  {
    label: 'Corsi For %',
    value: 'CF%_1',
    rank: 'CF%',
    percent: true,
  },
  {
    label: 'Goals For %',
    value: 'GF%_1',
    rank: 'GF%',
    percent: true,
  },
  {
    label: 'Expected Goals For %',
    value: 'xGF%_1',
    rank: 'xGF%',
    percent: true,
  },
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
];

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

          return (
            <section className="matchup-card" key={id}>
              <div className="matchup-summary">
                <div className="team-summary">
                  <span className="team-side">AWAY</span>
                  <h3>{away.Team}</h3>
                  <span className="goalie">
                    Goalie: {away.Goalie || 'Unknown'}
                  </span>
                  <span className="goalie-rank">
                    Goalie rank: {away.Goalie_Rank || 'N/A'}
                  </span>
                </div>

                <div className="versus">VS</div>

                <div className="team-summary home-team">
                  <span className="team-side">HOME</span>
                  <h3>{home.Team}</h3>
                  <span className="goalie">
                    Goalie: {home.Goalie || 'Unknown'}
                  </span>
                  <span className="goalie-rank">
                    Goalie rank: {home.Goalie_Rank || 'N/A'}
                  </span>
                </div>

                <button
                  className="details-button"
                  onClick={() => toggleRow(id)}
                  aria-expanded={isExpanded}
                >
                  {isExpanded ? 'Hide stats ▲' : 'Compare stats ▼'}
                </button>
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
                    {metrics.map((metric) => {
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
    </div>
  );
}

export default StatsTable;

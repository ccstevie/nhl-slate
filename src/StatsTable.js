
// src/StatsTable.js
import React, { useEffect, useState } from 'react';
import Papa from 'papaparse';
import './StatsTable.css';

function StatsTable() {
  const [data, setData] = useState([]);
  const [expandedRows, setExpandedRows] = useState({});

  useEffect(() => {
    fetch('/result.csv')
      .then((response) => response.text())
      .then((text) => {
        const parsedData = Papa.parse(text, {
          header: true,
          skipEmptyLines: true,
        });

        setData(parsedData.data);
      });
  }, []);

  // These columns will appear in the expandable details instead.
  const detailColumns = [
    'CF/60',
    'CA/60',
    'xGF/60',
    'xGA/60',
    'CF%_1',
    'GF%_1',
    'xGF%_1',
    'HDCF%_1',
    'SH%_1',
  ];

  const columns = data.length > 0
    ? Object.keys(data[0]).filter(
        (key) => key && !detailColumns.includes(key)
      )
    : [];

  const toggleRow = (index) => {
    setExpandedRows((previous) => ({
      ...previous,
      [index]: !previous[index],
    }));
  };

  const detailLabels = {
    'CF/60': 'Corsi For / 60',
    'CA/60': 'Corsi Against / 60',
    'xGF/60': 'Expected Goals For / 60',
    'xGA/60': 'Expected Goals Against / 60',
    'CF%_1': 'Corsi For %',
    'GF%_1': 'Goals For %',
    'xGF%_1': 'Expected Goals For %',
    'HDCF%_1': 'High Danger Chances For %',
    'SH%_1': 'Shooting %',
  };

  return (
    <div className="stats-container">
      <h2>Today's Hockey Matchups</h2>

      <table className="stats-table">
        <thead>
          <tr>
            {columns.map((key) => (
              <th key={key}>{key}</th>
            ))}
            <th>Details</th>
          </tr>
        </thead>

        <tbody>
          {data.map((row, index) => (
            <React.Fragment key={index}>
              <tr
                className={
                  index % 2 === 1 ? 'matchup-end' : 'matchup-start'
                }
              >
                {columns.map((key) => (
                  <td key={key}>{row[key]}</td>
                ))}

                <td>
                  <button
                    className="details-button"
                    onClick={() => toggleRow(index)}
                  >
                    {expandedRows[index] ? 'Hide ▲' : 'Stats ▼'}
                  </button>
                </td>
              </tr>

              {expandedRows[index] && (
                <tr className="details-row">
                  <td colSpan={columns.length + 1}>
                    <div className="details-content">
                      <h4>Advanced Team Statistics</h4>

                      <div className="details-grid">
                        {detailColumns.map((key) => (
                          <div className="detail-item" key={key}>
                            <span className="detail-label">
                              {detailLabels[key]}
                            </span>
                            <strong>{row[key] || 'N/A'}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default StatsTable;

// src/StatsTable.js
import React, { useEffect, useState } from 'react';
import Papa from 'papaparse';
import './StatsTable.css';

function StatsTable() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('/result.csv')
      .then((response) => response.text())
      .then((text) => {
        const parsedData = Papa.parse(text, { header: true });
        setData(parsedData.data);
      });
  }, []);

  return (
    <div>
      <h2>Today's Hockey Matchups</h2>
      <table>
        <thead>
          <tr>
            {data.length > 0 && Object.keys(data[0]).map((key) => <th key={key}>{key}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={index} className={index % 2 === 1 ? 'matchup-end' : 'matchup-start'}>
              {Object.values(row).map((val, i) => (
                <td key={i}>{val}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default StatsTable;

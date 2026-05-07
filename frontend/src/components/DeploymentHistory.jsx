export default function DeploymentHistory({ history }) {
    return (
      <div className="card">
        <div className="card-title">◎ Deployment History</div>
        <table className="table">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Branch</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {history.map(d => (
              <tr key={d.id}>
                <td style={{ color: "var(--text-primary)" }}>{d.repo}</td>
                <td>{d.branch}</td>
                <td>
                  <span className={`badge badge-${d.status}`}>
                    {d.status === "success" ? "✓" : d.status === "failed" ? "✗" : "○"} {d.status}
                  </span>
                </td>
                <td>{d.duration}</td>
                <td>{d.time}</td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "var(--text-dim)" }}>
                  No deployments yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    );
  }
  
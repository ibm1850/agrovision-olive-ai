export default function QuickActionGrid({ actions = [] }) {
  return (
    <div className="quick-action-grid">
      {actions.map((action) => (
        <button key={action.id} className="quick-action-card" onClick={action.onClick}>
          <h4>{action.title}</h4>
          <p>{action.body}</p>
        </button>
      ))}
    </div>
  );
}

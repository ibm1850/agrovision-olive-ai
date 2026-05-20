export default function StatCard({ label, value, hint = "", tone = "neutral" }) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <p>{label}</p>
      <h3>{value}</h3>
      {hint ? <small>{hint}</small> : null}
    </article>
  );
}

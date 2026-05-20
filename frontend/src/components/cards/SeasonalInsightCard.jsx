export default function SeasonalInsightCard({ title, detail, value }) {
  return (
    <div className="seasonal-card">
      <p className="eyebrow">{title}</p>
      <h4>{value}</h4>
      <p className="subtle">{detail}</p>
    </div>
  );
}

export default function SkySelect({
  categories,
  category,
  counts,
  onCategory,
  id = 'sky-select',
}) {
  return (
    <label className="sky-select" htmlFor={id}>
      <span>Sky</span>
      <select
        id={id}
        value={category}
        onChange={(event) => onCategory(event.target.value)}
        aria-label="Choose which topics fill the sky"
      >
        <option value="all">All topics</option>
        {categories.map((name) => (
          <option key={name} value={name}>
            {name}
            {counts?.[name] != null ? ` (${counts[name]})` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}

import { SOLAR_SYSTEM_LABEL } from '../lib/copy'

export default function SkySelect({
  categories,
  category,
  counts,
  onCategory,
  id = 'sky-select',
}) {
  return (
    <label className="sky-select" htmlFor={id}>
      <span>{SOLAR_SYSTEM_LABEL}</span>
      <select
        id={id}
        value={category}
        onChange={(event) => onCategory(event.target.value)}
        aria-label="Choose which topics fill the solar system"
      >
        <option value="all">All topics</option>
        {categories
          .filter((name) => name === category || (counts?.[name] ?? 0) > 0)
          .map((name) => (
            <option key={name} value={name}>
              {name}
              {counts?.[name] != null ? ` (${counts[name]})` : ''}
            </option>
          ))}
      </select>
    </label>
  )
}

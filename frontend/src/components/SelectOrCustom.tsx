export const CUSTOM = "__custom__";

interface SelectOrCustomProps {
  value: string;
  onValueChange: (value: string) => void;
  customValue: string;
  onCustomChange: (value: string) => void;
  options: string[];
  disabled?: boolean;
  placeholder: string;
  customPlaceholder: string;
  optionLabel?: (value: string) => string;
  className?: string;
}

export default function SelectOrCustom({
  value,
  onValueChange,
  customValue,
  onCustomChange,
  options,
  disabled = false,
  placeholder,
  customPlaceholder,
  optionLabel,
  className,
}: SelectOrCustomProps) {
  const isCustom = value === CUSTOM;

  return (
    <>
      <select
        className={className}
        value={isCustom ? CUSTOM : value}
        disabled={disabled}
        onChange={(e) => onValueChange(e.target.value)}
      >
        <option value="">{placeholder}</option>

        {options.map((opt) => (
          <option key={opt} value={opt}>
            {optionLabel ? optionLabel(opt) : opt}
          </option>
        ))}

        <option value={CUSTOM}>Others (type your own)</option>
      </select>

      {isCustom && (
        <input
          className={className}
          type="text"
          value={customValue}
          placeholder={customPlaceholder}
          onChange={(e) => onCustomChange(e.target.value)}
          style={{
            marginTop: "8px",
            boxSizing: "border-box",
            font: "inherit",
            width: "100%",
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid #cbd5e1",
          }}
        />
      )}
    </>
  );
}
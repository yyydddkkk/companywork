interface SegmentedControlProps<T extends string> {
  options: Array<{ label: string; value: T }>;
  value: T;
  onChange: (value: T) => void;
}

export default function SegmentedControl<T extends string>({ options, value, onChange }: SegmentedControlProps<T>) {
  return (
    <div className="segmented" role="tablist" aria-label="View switch">
      {options.map((option) => (
        <button
          key={option.value}
          className={option.value === value ? 'segmented-btn active' : 'segmented-btn'}
          role="tab"
          aria-selected={option.value === value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

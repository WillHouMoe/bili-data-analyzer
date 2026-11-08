export interface AutoScaleOptions {
  /** Fraction of the data span added above and below the observed values. */
  padding?: number;
  /** Keep a non-negative axis at zero instead of narrowing around the data. */
  includeZero?: boolean;
}

export interface AutoScaleRange {
  min: number;
  max: number;
}

function trim(value: number, digits: number): string {
  const fixed = value.toFixed(digits);
  return fixed.includes(".")
    ? fixed.replace(/0+$/, "").replace(/\.$/, "")
    : fixed;
}

function niceStep(span: number): number {
  if (!Number.isFinite(span) || span <= 0) return 1;
  return 10 ** Math.floor(Math.log10(span));
}

function compactPrecision(scaledSpan: number): number {
  if (!Number.isFinite(scaledSpan) || scaledSpan <= 0) return 0;
  return Math.max(0, Math.ceil(-Math.log10(Math.abs(scaledSpan) / 5)));
}

/**
 * Narrow an axis to the observed values with readable headroom. Positive data
 * never produces a negative minimum; `includeZero` opts back into a zero base.
 */
export function autoScaleRange(
  values: number[],
  { padding = 0.1, includeZero = false }: AutoScaleOptions = {},
): AutoScaleRange {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) {
    return { min: 0, max: 1 };
  }

  const observedMin = Math.min(...finite);
  const observedMax = Math.max(...finite);
  const span = observedMax - observedMin;
  const pad = span > 0
    ? span * padding
    : Math.max(Math.abs(observedMax) * 0.05, 1);
  let min = observedMin - pad;
  let max = observedMax + pad;

  if (!includeZero && observedMin >= 0) {
    min = Math.max(0, min);
  }
  if (includeZero) {
    min = Math.min(0, min);
    max = Math.max(0, max);
  }
  if (min === max) {
    min -= 1;
    max += 1;
  }

  const step = niceStep(max - min);
  return {
    min: Math.floor(min / step) * step,
    max: Math.ceil(max / step) * step,
  };
}

/** Compact labels that retain enough decimals for a narrowed axis span. */
export function scaledNumber(value: number, span: number): string {
  const magnitude = Math.abs(value);

  if (magnitude >= 1_000_000_000) {
    return `${trim(value / 1_000_000_000, compactPrecision(span / 1_000_000_000))}B`;
  }
  if (magnitude >= 1_000_000) {
    return `${trim(value / 1_000_000, compactPrecision(span / 1_000_000))}M`;
  }
  if (magnitude >= 1_000) {
    return `${trim(value / 1_000, compactPrecision(span / 1_000))}K`;
  }
  return trim(value, compactPrecision(span));
}

/** Decimal precision for a narrowed percentage axis. */
export function scaledDecimal(value: number, span: number): string {
  return value.toFixed(compactPrecision(span));
}

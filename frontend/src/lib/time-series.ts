export function toTimedSeries<T>(
  points: T[],
  timestamp: (point: T) => string,
  value: (point: T) => number,
): Array<[number, number]> {
  return points
    .map((point) => [Date.parse(timestamp(point)), value(point)] as const)
    .filter(([time]) => Number.isFinite(time))
    .sort(([left], [right]) => left - right)
    .map(([time, reading]) => [time, reading]);
}

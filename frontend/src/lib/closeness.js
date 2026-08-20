export const NUM_BUCKETS = 20

const TEMPERATURES = ['Ice cold', 'Cold', 'Cool', 'Lukewarm', 'Warm', 'Hot', 'Scorching']

// bucket 0 (coldest) -> hue 240 (blue), bucket 19 (hottest) -> hue 0 (red),
// sweeping the long way through cyan/green/yellow/orange for a wider,
// more differentiated range of shades across the 20 buckets.
export function bucketColor(bucket) {
  const hue = 240 - (bucket / (NUM_BUCKETS - 1)) * 240
  return `hsl(${hue}, 75%, 50%)`
}

export function temperatureLabel(bucket) {
  const index = Math.min(TEMPERATURES.length - 1, Math.floor((bucket / NUM_BUCKETS) * TEMPERATURES.length))
  return TEMPERATURES[index]
}

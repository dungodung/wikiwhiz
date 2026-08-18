const NUM_BUCKETS = 20

// bucket 0 (coldest) -> hue 220 (blue), bucket 19 (hottest) -> hue 0 (red)
function bucketColor(bucket) {
  const hue = 220 - (bucket / (NUM_BUCKETS - 1)) * 220
  return `hsl(${hue}, 75%, 50%)`
}

export default function ClosenessGradientBar({ bucket }) {
  return (
    <div className="closeness-bar" aria-label="Lexical closeness">
      <div className="closeness-bar__track">
        {Array.from({ length: NUM_BUCKETS }).map((_, i) => (
          <span
            key={i}
            className="closeness-bar__segment"
            style={{
              backgroundColor: bucketColor(i),
              opacity: bucket == null ? 0.15 : i <= bucket ? 1 : 0.15,
            }}
          />
        ))}
      </div>
      <span className="closeness-bar__label">
        {bucket == null ? 'Lexical closeness' : `${Math.round(((bucket + 1) / NUM_BUCKETS) * 100)}% close`}
      </span>
    </div>
  )
}

import { NUM_BUCKETS, bucketColor, temperatureLabel } from '../../lib/closeness'

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
      <span className="closeness-bar__label">{bucket == null ? 'Lexical closeness' : temperatureLabel(bucket)}</span>
    </div>
  )
}

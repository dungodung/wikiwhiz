export function wikipediaUrl(title) {
  return `https://en.wikipedia.org/wiki/${encodeURIComponent(title.replace(/ /g, '_'))}`
}

// Login is "with Wikimedia" (a global SUL account, not enwiki-specific),
// but this app's whole identity is English-Wikipedia-flavored (see
// wikipediaUrl above) and that's where an admin reviewing a player would
// actually recognize edits/contributions, so User: links point there too
// rather than to meta.wikimedia.org.
export function wikipediaUserUrl(username) {
  return `https://en.wikipedia.org/wiki/User:${encodeURIComponent(username.replace(/ /g, '_'))}`
}

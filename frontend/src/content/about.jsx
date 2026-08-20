// Static "about the game / about the author" content. No API call needed --
// see backend/app/blueprints/info/routes.py for why this lives client-side.
export default function AboutContent() {
  return (
    <>
      <h2>About WikiWhiz</h2>
      <p>
        WikiWhiz is a daily guessing game built on English Wikipedia, Wikidata,
        Wikimedia Commons, and Wiktionary. Each day has one puzzle: guess the
        Wikipedia article behind a series of clues, ranging from obscure
        categories to infobox facts to a photo from the article. Every guess
        shows two kinds of "closeness" — how lexically similar your guess is to
        the answer, and how many Wikipedia links separate the two articles
        ("degrees of Wikipedia").
      </p>
      <p>
        A new challenge appears every day at 00:00 UTC. You can play anonymously,
        or log in with your Wikimedia account to keep stats across days.
      </p>
      <h2>About the author</h2>
      <p>
        WikiWhiz is an independent, community-run Wikimedia Toolforge project
        built by Filip Maljković (
        <a href="https://en.wikipedia.org/wiki/User:Dungodung" target="_blank" rel="noopener noreferrer">
          User:Dungodung
        </a>
        ). Source code and issue tracking live on the project's GitLab repository.
      </p>
    </>
  )
}

const CLUE_TYPE_LABELS = {
  commons_image: 'Photo',
  dyk_or_notable_fact: 'Did you know',
  wikidata_fact: 'Wikidata fact',
  infobox_fact: 'Infobox fact',
  categories: 'Categories',
  etymology: 'Etymology',
  wikisource_excerpt: 'Wikisource excerpt',
  wikivoyage_fact: 'Wikivoyage fact',
  pageviews: 'Pageviews',
  top_citation: 'Notable reference',
  incoming_links: 'Linked from',
  long_section_title: 'Section title',
  creation_year: 'Article age',
  langlinks_count: 'Language coverage',
}

export default function ClueCard({ clue, index }) {
  return (
    <li className="clue-card">
      <div className="clue-card__header">
        <span className="clue-card__index">Clue {index + 1}</span>
        <span className="clue-card__type">{CLUE_TYPE_LABELS[clue.clue_type] || clue.clue_type}</span>
      </div>
      {clue.clue_media_url && (
        <img className="clue-card__image" src={clue.clue_media_url} alt="" loading="lazy" />
      )}
      <p className="clue-card__text">{clue.clue_text}</p>
    </li>
  )
}

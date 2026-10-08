/**
 * Registry of slide decks published under /slides/. Each deck is a bespoke page in `pages/slides/`;
 * this list only drives the index page and the deck header.
 */
export interface DeckEntry {
  slug: string;
  title: string;
  summary: string;
  venue: string;
  date: string;
}

export const DECKS: DeckEntry[] = [
  {
    slug: 'hegota-scope',
    title: 'Hegotá scope against previous forks',
    summary: 'How much complexity Hegotá has accumulated so far, compared with what previous forks took to ship.',
    venue: 'All Core Devs',
    date: '2026-10-08',
  },
];

export function deck(slug: string): DeckEntry {
  const entry = DECKS.find((item) => item.slug === slug);
  if (!entry) throw new Error(`Unknown deck ${slug}`);
  return entry;
}

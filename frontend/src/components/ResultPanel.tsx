import type { ReactNode } from 'react';
import { ArrowUpRight, Plane, Star } from 'lucide-react';
import { formatPrice, reasonText, siteLabel } from '../lib/present';
import type { AgentResult, Offer, SiteRun } from '../lib/present';
import { parseFlight } from '../lib/flight';
import type { Flight } from '../lib/flight';
import { countedNoun, countPhrase, missingModels, parseProductAnswer } from '../lib/answer';
import type { ProductAnswer } from '../lib/answer';

interface ResultPanelProps {
  result: AgentResult | null;
  subject?: string;
  taskType?: string;
  query?: string;
}

export function ResultPanel({ result, subject, taskType, query }: ResultPanelProps) {
  if (!result) return null;
  const data = result.extracted_data ?? {};
  return (
    <section className="flex flex-col gap-6">
      {Array.isArray(data.offers)
        ? <ComparisonResult result={result} subject={subject} taskType={taskType} />
        : <BrowsingResult result={result} subject={subject} query={query} />}
    </section>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="text-sm font-medium text-muted">{children}</span>;
}

function Headline({ children }: { children: ReactNode }) {
  return <h2 className="mt-1 font-display text-3xl font-medium leading-tight tracking-tight text-ink sm:text-4xl">{children}</h2>;
}

function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function ComparisonResult({ result, subject, taskType }: { result: AgentResult; subject?: string; taskType?: string }) {
  const data = result.extracted_data ?? {};
  const offers: Offer[] = data.offers ?? [];
  const sites: SiteRun[] = data.sites ?? [];
  const warnings: string[] = data.warnings ?? [];
  // The backend lists offers that cannot be bought (Coming Soon, Out of
  // Stock) last, labelled; they are never the lowest price.
  const buyable = offers.filter((offer) => !offer.availability);
  const unbuyable = offers.filter((offer) => offer.availability);
  // Older backends do not send matched; there, the ranked offers matched.
  const matched = data.matched ?? true;
  const best = matched ? buyable[0] : undefined;
  const firstLine = String(data.answer ?? '').split('\n')[0];
  const sitesChecked = sites.map((site) => siteLabel(site.site)).join(' and ');

  return (
    <>
      <div>
        {best ? (
          <>
            <Eyebrow>{taskType === 'compare' ? 'Lowest price' : 'Cheapest result'}{subject ? ` for ${subject}` : ''}</Eyebrow>
            <Headline>
              <span className="text-deal">{formatPrice(best.price, best.currency)}</span> on {siteLabel(best.site)}
            </Headline>
            <p className="mt-2 text-muted">
              {buyable.length} {buyable.length === 1 ? 'offer' : 'offers'} you can buy
              {sitesChecked && `, from ${sitesChecked}`}. Sorted by price.
            </p>
          </>
        ) : (
          <>
            <Eyebrow>{result.completed ? 'No matching offer' : "Couldn't read the results"}</Eyebrow>
            <Headline>{result.completed ? firstLine : reasonText(result.reason)}</Headline>
          </>
        )}
      </div>

      {buyable.length > 0 && (
        <div>
          {!matched && <h3 className="mb-2 text-sm font-medium text-muted">Offers found, none meeting your request</h3>}
          <OfferList offers={buyable} best={best} />
        </div>
      )}

      {unbuyable.length > 0 && (
        <details open={buyable.length === 0} className="group">
          <summary className="cursor-pointer text-sm text-muted hover:text-ink">
            {unbuyable.length} more listed but can't be bought right now
            ({[...new Set(unbuyable.map((offer) => offer.availability))].join(', ')})
          </summary>
          <div className="mt-3 opacity-70">
            <OfferList offers={unbuyable} />
          </div>
        </details>
      )}

      <SiteNotes sites={sites} warnings={warnings} />
    </>
  );
}

function OfferList({ offers, best }: { offers: Offer[]; best?: Offer }) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
      {offers.map((offer) => {
        const isBest = offer === best;
        const extra = best?.price != null && offer.price != null && !isBest ? offer.price - best.price : null;
        return (
          <li key={`${offer.site}-${offer.product_url}`} className={isBest ? 'bg-deal-soft' : undefined}>
            <a
              href={offer.product_url}
              target="_blank"
              rel="noreferrer"
              className="group flex gap-4 px-4 py-4 transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent sm:px-5"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold text-ink">{siteLabel(offer.site)}</span>
                  {isBest && (
                    <span className="rounded-full bg-deal px-2 py-0.5 text-xs font-semibold text-surface">Lowest</span>
                  )}
                  {offer.availability && (
                    <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">{offer.availability}</span>
                  )}
                </div>
                <p className="mt-1 line-clamp-2 text-ink/90">{offer.title}</p>
                {offer.rating != null && (
                  <p className="mt-1 flex items-center gap-1 text-sm text-muted">
                    <Star size={14} className="fill-current text-deal-bar" />
                    {offer.rating}
                    {offer.review_count != null && <span>· {offer.review_count.toLocaleString('en-IN')} ratings</span>}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-end justify-between text-right">
                <span className="font-display text-xl font-medium tabular-nums text-ink">
                  {formatPrice(offer.price, offer.currency)}
                </span>
                {extra != null && extra > 0 && (
                  <span className="text-sm tabular-nums text-muted">+{formatPrice(extra, offer.currency)}</span>
                )}
                <span className="mt-1 flex items-center gap-0.5 text-sm text-accent opacity-70 group-hover:opacity-100">
                  Open <ArrowUpRight size={14} />
                </span>
              </div>
            </a>
          </li>
        );
      })}
    </ul>
  );
}

const SITE_STATUS: Record<string, string> = {
  blocked: 'showed a sign-in or CAPTCHA page, so it was skipped',
  failed: 'could not be read',
};

function SiteNotes({ sites, warnings }: { sites: SiteRun[]; warnings: string[] }) {
  const problems = sites.filter((site) => site.status !== 'completed');
  if (problems.length === 0 && warnings.length === 0) return null;
  return (
    <div className="rounded-xl border border-line px-4 py-3 text-sm text-muted">
      {problems.map((site) => (
        <p key={site.site}>{siteLabel(site.site)} {SITE_STATUS[site.status] ?? site.status}.</p>
      ))}
      {warnings.map((warning) => <p key={warning}>{warning}</p>)}
    </div>
  );
}

function BrowsingResult({ result, subject, query }: { result: AgentResult; subject?: string; query?: string }) {
  const { answer, answer_parts: parts, ...rest } = result.extracted_data ?? {};
  const details = Object.entries(rest);
  const steps = `${result.iterations} ${result.iterations === 1 ? 'step' : 'steps'}`;
  const read: string[] = result.completed && Array.isArray(parts) ? parts : [];
  // "How many" is answered by counting what was read; see countedNoun.
  const noun = read.length > 0 ? countedNoun(query) : null;
  const flight = !noun && read.length > 0 ? parseFlight(read, subject) : null;
  const product = !noun && !flight && read.length > 0 ? parseProductAnswer(read) : null;
  // Several values that are neither a flight nor a product read as a list.
  const items = noun || (!flight && !product && read.length > 1) ? read : [];
  const source = result.last_url ? hostOf(result.last_url) : undefined;

  return (
    <>
      <div>
        {flight ? (
          <FlightSummary flight={flight} cheapest={/\bcheapest\b/i.test(subject ?? '')} />
        ) : product ? (
          <ProductSummary answer={product} source={source} />
        ) : noun ? (
          <>
            <Eyebrow>Answer{source ? ` from ${source}` : ''}</Eyebrow>
            <Headline>{countPhrase(read.length, noun)}</Headline>
          </>
        ) : items.length > 0 ? (
          <Eyebrow>Answer{source ? ` from ${source}` : ''} · {steps}</Eyebrow>
        ) : result.completed ? (
          <>
            <Eyebrow>Answer · {steps}</Eyebrow>
            <Headline>{answer ? String(answer) : 'Done. Nothing was read back from the page.'}</Headline>
          </>
        ) : (
          <>
            <Eyebrow>Couldn't finish · {steps}</Eyebrow>
            <Headline>{reasonText(result.reason)}</Headline>
          </>
        )}
      </div>

      {flight && <FlightCard flight={flight} />}
      {product && <ProductCard answer={product} subject={subject} />}
      {items.length > 0 && (
        <ul className={`divide-y divide-line rounded-2xl border border-line bg-surface ${noun ? '' : '-mt-4'}`}>
          {items.map((item, index) => (
            <li key={`${index}-${item}`} className="px-5 py-3 text-lg text-ink">{item}</li>
          ))}
        </ul>
      )}

      {result.last_url && (
        <a
          href={result.last_url}
          target="_blank"
          rel="noreferrer"
          className="-mt-2 inline-flex items-center gap-1 self-start text-accent underline-offset-4 hover:underline"
        >
          {flight ? 'See this flight' : 'Open the page'} on {hostOf(result.last_url)} <ArrowUpRight size={16} />
        </a>
      )}

      {details.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-muted">
            {result.completed ? 'Also read from the page' : 'Read before it stopped'}
          </h3>
          <dl className="divide-y divide-line rounded-2xl border border-line bg-surface">
            {details.map(([key, value]) => (
              <div key={key} className="flex flex-col gap-0.5 px-5 py-3 sm:flex-row sm:gap-6">
                <dt className="shrink-0 text-sm text-muted sm:w-40">{key.replace(/_/g, ' ')}</dt>
                <dd className="text-ink">{typeof value === 'string' ? value : JSON.stringify(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </>
  );
}

function ProductSummary({ answer, source }: { answer: ProductAnswer; source?: string }) {
  const where = source ? ` on ${source}` : '';
  if (answer.rating == null) {
    return (
      <>
        <Eyebrow>Price{where}</Eyebrow>
        <Headline><span className="text-deal">{answer.price}</span></Headline>
      </>
    );
  }
  return (
    <>
      <Eyebrow>Rating{where}</Eyebrow>
      <Headline>
        {answer.rating} <span className="text-muted">out of 5</span>
      </Headline>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-muted">
        <Stars rating={answer.rating} />
        {answer.ratingCount && <span>{answer.ratingCount}</span>}
      </div>
    </>
  );
}

/** Five stars, filled to the rating (4.6 fills four and most of the fifth). */
function Stars({ rating }: { rating: number }) {
  const fill = `${Math.max(0, Math.min(rating, 5)) * 20}%`;
  const row = (className: string) => (
    <span className={`flex gap-0.5 ${className}`}>
      {[0, 1, 2, 3, 4].map((index) => <Star key={index} size={20} className="shrink-0 fill-current" />)}
    </span>
  );
  return (
    <span className="relative inline-flex" role="img" aria-label={`${rating} out of 5 stars`}>
      {row('text-line')}
      <span className="absolute inset-y-0 left-0 overflow-hidden" style={{ width: fill }}>
        {row('text-deal-bar')}
      </span>
    </span>
  );
}

function ProductCard({ answer, subject }: { answer: ProductAnswer; subject?: string }) {
  const missing = missingModels(subject, answer.product);
  if (!answer.product && !answer.other.length && !(answer.price && answer.rating != null)) return null;
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl border border-line bg-surface px-5 py-4">
        <div className="flex gap-4">
          {answer.product && <p className="min-w-0 flex-1 text-ink">{answer.product}</p>}
          {answer.price && answer.rating != null && (
            <span className="shrink-0 font-display text-xl font-medium tabular-nums text-ink">{answer.price}</span>
          )}
        </div>
        {answer.other.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {answer.other.map((part) => (
              <span key={part} className="rounded-full border border-line px-2.5 py-0.5 text-sm text-muted">{part}</span>
            ))}
          </div>
        )}
      </div>
      {missing.length > 0 && (
        <p className="rounded-xl bg-deal-soft px-4 py-3 text-sm text-ink">
          This may not be the product you asked for: its title does not mention{' '}
          {missing.map((token) => `“${token.toUpperCase()}”`).join(' or ')}.
        </p>
      )}
    </div>
  );
}

function FlightSummary({ flight, cheapest }: { flight: Flight; cheapest: boolean }) {
  const route = flight.from && flight.to ? `, ${flight.from} to ${flight.to}` : '';
  return (
    <>
      <Eyebrow>{cheapest ? 'Cheapest flight' : 'Flight found'}{route}</Eyebrow>
      <Headline>
        <span className="text-deal">{flight.price}</span>
        {flight.airline && <> on {flight.airline}</>}
      </Headline>
      {(flight.tripType || flight.date) && (
        <p className="mt-2 text-muted">{[flight.tripType, flight.date].filter(Boolean).join(' · ')}</p>
      )}
    </>
  );
}

/** Departure and arrival, with the stops between them, as a boarding-pass row. */
function FlightCard({ flight }: { flight: Flight }) {
  const between = [flight.stops, flight.duration].filter(Boolean).join(' · ');
  return (
    <div className="rounded-2xl border border-line bg-surface px-5 py-5 sm:px-6">
      <div className="flex items-center gap-4 sm:gap-6">
        <FlightEnd time={flight.departs} place={flight.from} label="Departs" />
        <div className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
          <span className="truncate text-sm text-muted">{between || ' '}</span>
          <div className="flex w-full items-center">
            <span className="h-2 w-2 shrink-0 rounded-full border-2 border-accent" />
            <span className="h-px flex-1 border-t border-dashed border-faint" />
            <Plane size={18} className="mx-1 shrink-0 rotate-45 text-accent" />
            <span className="h-px flex-1 border-t border-dashed border-faint" />
            <span className="h-2 w-2 shrink-0 rounded-full bg-accent" />
          </div>
        </div>
        <FlightEnd time={flight.arrives} place={flight.to} label="Arrives" align="right" />
      </div>
      {flight.other.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
          {flight.other.map((part) => (
            <span key={part} className="rounded-full border border-line px-2.5 py-0.5 text-sm text-muted">{part}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function FlightEnd({ time, place, label, align }: { time: string; place?: string; label: string; align?: 'right' }) {
  return (
    <div className={`shrink-0 ${align === 'right' ? 'text-right' : ''}`}>
      <span className="block text-xs font-medium uppercase tracking-wide text-faint">{label}</span>
      <span className="block font-display text-2xl font-medium tabular-nums text-ink sm:text-3xl">{time}</span>
      {place && <span className="block text-sm text-muted">{place}</span>}
    </div>
  );
}

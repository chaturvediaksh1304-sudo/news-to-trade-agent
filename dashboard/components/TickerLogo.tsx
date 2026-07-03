"use client";

import { useState } from "react";

// Company logo by ticker via Parqet's public logo CDN; falls back to a
// monogram badge if the symbol has no logo.
export default function TickerLogo({ ticker }: { ticker: string }) {
  const [failed, setFailed] = useState(false);

  return (
    <span className="tlogo" title={ticker}>
      {failed ? (
        <span className="fallback">{ticker[0]}</span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`https://assets.parqet.com/logos/symbol/${ticker}?format=png&size=64`}
          alt={`${ticker} logo`}
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}

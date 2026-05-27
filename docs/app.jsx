/* International News Digest — main app
   Asymmetric Mosaic editorial design wired to live data with
   category + date filters. Click anywhere on a card to open source. */

const { useState, useMemo, useEffect } = React;

// —— utilities ——
const CAT_LABELS = {
  international: { zh: "國際", en: "World" },
  tech:          { zh: "科技", en: "Tech" },
  finance:       { zh: "財經", en: "Finance" },
  games:         { zh: "遊戲業", en: "Games" },
};
const CAT_COLOR = {
  international: "var(--crimson)",
  tech:          "var(--olive)",
  finance:       "var(--ochre)",
  games:         "var(--terracotta)",
};

function dateLabel(d) {
  const today = new Date().toLocaleDateString("sv-SE");
  const yest  = new Date(Date.now() - 86400000).toLocaleDateString("sv-SE");
  if (d === today) return "今天";
  if (d === yest)  return "昨天";
  const [, m, day] = d.split("-");
  return `${+m}/${+day}`;
}
function dateLabelLong(d) {
  const [, m, day] = d.split("-");
  const w = ["日","一","二","三","四","五","六"][new Date(d).getDay()];
  return `${+m}月${+day}日 · 週${w}`;
}

// —— small primitives ——
function CatDot({ cat }) {
  return <span className="cat-dot" style={{ background: CAT_COLOR[cat] }} />;
}
function Meta({ a, tone }) {
  return (
    <div className="t-meta" data-tone={tone}>
      <CatDot cat={a.category} />
      <span>{CAT_LABELS[a.category].zh}</span>
      <span className="t-src">{a.source}</span>
    </div>
  );
}
function ImpactPanel({ text, tone }) {
  return (
    <div className="t-impact" data-tone={tone}>
      <div className="t-impact-lbl">對遊戲業</div>
      <p>{text}</p>
    </div>
  );
}

// —— Hero tile (largest critical) ——
function HeroTile({ a }) {
  if (!a) return null;
  return (
    <a className="t hero" href={a.url} target="_blank" rel="noopener" data-tone="terra">
      <div className="t-eye">
        <span className="t-pill">必看頭條</span>
        <span>{CAT_LABELS[a.category].zh}</span>
        <span className="t-src">{a.source}</span>
        <span className="t-date">{a.date}</span>
      </div>
      <h2 className="t-hero-title">{a.title_zh || a.title_original}</h2>
      <div className="t-hero-split">
        <div className="t-hero-panel">
          <div className="t-hero-lbl">摘要</div>
          <p>{a.summary_zh}</p>
        </div>
        {a.game_impact && (
          <div className="t-hero-panel">
            <div className="t-hero-lbl">對遊戲業</div>
            <p>{a.game_impact}</p>
          </div>
        )}
      </div>
      <span className="t-read">閱讀原文 →</span>
    </a>
  );
}

// —— Critical secondary tile ——
function CritTile({ a }) {
  if (!a) return null;
  return (
    <a className="t crit" href={a.url} target="_blank" rel="noopener" data-tone="ochre">
      <div className="t-eye">
        <span className="t-pill">必看</span>
        <span>{CAT_LABELS[a.category].zh}</span>
        <span className="t-src">{a.source}</span>
      </div>
      <h3 className="t-crit-title">{a.title_zh || a.title_original}</h3>
      <div className="t-crit-panel">
        <div className="t-crit-lbl">摘要</div>
        <p>{a.summary_zh}</p>
      </div>
      {a.game_impact && (
        <div className="t-crit-panel">
          <div className="t-crit-lbl">對遊戲業</div>
          <p>{a.game_impact}</p>
        </div>
      )}
      <span className="t-read">閱讀原文 →</span>
    </a>
  );
}

// —— Normal tile ——
function NormalTile({ a, tone, wide }) {
  return (
    <a
      className={`t normal ${wide ? "wide" : ""}`}
      href={a.url}
      target="_blank"
      rel="noopener"
      data-tone={tone}
    >
      <Meta a={a} tone={tone} />
      <h3 className="t-normal-title">{a.title_zh || a.title_original}</h3>
      <p className="t-sum">{a.summary_zh}</p>
      {a.game_impact && <ImpactPanel text={a.game_impact} tone={tone} />}
      <span className="t-read">閱讀原文 →</span>
    </a>
  );
}

// —— Background tile ——
function BgTile({ a }) {
  return (
    <a className="t bg" href={a.url} target="_blank" rel="noopener" data-tone="paper-deep">
      <div className="t-bg-meta">
        <CatDot cat={a.category} />
        <span>{CAT_LABELS[a.category].zh}</span>
        <span className="dot-sep">·</span>
        <span>{a.source}</span>
        <span className="dot-sep">·</span>
        <span>{a.date.slice(5)}</span>
      </div>
      <h4 className="t-bg-title">{a.title_zh || a.title_original}</h4>
      <p className="t-bg-sum">{a.summary_zh}</p>
      {a.game_impact && <p className="t-bg-impact">對遊戲業｜{a.game_impact}</p>}
    </a>
  );
}

// —— Pattern for normal mosaic: tone + wide flag per index ——
// Cream-led rotation so most tiles stay paper-toned, with darker accents
// dropped in at fixed offsets. Wide-2 is *content-gated* — only articles
// with enough body + game-impact text earn the larger footprint, paced so
// roughly one in four long articles goes wide.
const TONE_CYCLE = ["paper-soft", "paper-deep", "olive", "paper-soft", "ink", "paper-deep"];
const WIDE_MIN_CHARS = 130; // summary + game_impact combined
function articleLen(a) {
  return (a.summary_zh?.length || 0) + (a.game_impact?.length || 0);
}

// —— App ——
function App() {
  const dates = useMemo(
    () => [...new Set(window.ALL_NEWS.map((a) => a.date))].sort().reverse().slice(0, 7),
    []
  );

  const [cat, setCat] = useState("all");
  const [date, setDate] = useState(dates[0]);

  const filtered = useMemo(
    () => window.ALL_NEWS.filter(
      (a) => (cat === "all" || a.category === cat) && (!date || a.date === date)
    ),
    [cat, date]
  );

  const critical   = filtered.filter((a) => a.importance === "critical");
  const normal     = filtered.filter((a) => !a.importance || a.importance === "normal");
  const background = filtered.filter((a) => a.importance === "background");

  // Top 2 critical = hero + secondary; remaining critical interleave into the
  // normal mosaic so they don't pile into a slab of identical terracotta blocks.
  const heroA = critical[0];
  const critB = critical[1];
  const extraCrits = critical.slice(2);

  // Interleave: insert one extra-critical after every 4 normals so they're
  // spaced through the mosaic but still appear near the top of the list.
  // Then assign tone + width per tile, with wide-2 only landing on articles
  // whose body is long enough to fill it.
  const mixed = useMemo(() => {
    const out = [];
    let ci = 0;
    normal.forEach((a, i) => {
      if (ci < extraCrits.length && i > 0 && i % 4 === 0) {
        out.push({ a: extraCrits[ci++], crit: true });
      }
      out.push({ a, crit: false });
    });
    while (ci < extraCrits.length) out.push({ a: extraCrits[ci++], crit: true });

    let critIdx = 0, normIdx = 0, longCritSeen = 0, longNormSeen = 0;
    return out.map((item) => {
      const contentful = articleLen(item.a) >= WIDE_MIN_CHARS;
      let tone, wide;
      if (item.crit) {
        tone = critIdx % 2 === 0 ? "terra" : "ochre";
        wide = false;
        if (contentful) {
          longCritSeen++;
          if (longCritSeen % 2 === 1) wide = true; // every other long critical
        }
        critIdx++;
      } else {
        tone = TONE_CYCLE[normIdx % TONE_CYCLE.length];
        wide = false;
        if (contentful) {
          longNormSeen++;
          if (longNormSeen % 4 === 0) wide = true; // every 4th long normal
        }
        normIdx++;
      }
      return { ...item, tone, wide };
    });
  }, [normal, extraCrits]);

  // Per-category counts for the pills
  const catCounts = useMemo(() => {
    const c = { all: 0, international: 0, tech: 0, finance: 0, games: 0 };
    filtered.concat(window.ALL_NEWS.filter((a) => a.date === date)).forEach(() => {});
    // We want counts within current date
    const inDate = window.ALL_NEWS.filter((a) => !date || a.date === date);
    inDate.forEach((a) => { c.all++; c[a.category]++; });
    return c;
  }, [date]);

  // Ribbon date: the most recent date present in the data set, formatted
  // editorial-style. Time is the user's real-world current time, refreshed
  // every minute so the "live" indicator feels alive without heavy re-render.
  const latestDate = dates[0];
  const ribbonDate = useMemo(() => {
    if (!latestDate) return "";
    const d = new Date(latestDate);
    const weekday = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"][d.getDay()];
    return `${latestDate.replace(/-/g, ".")} · ${weekday}`;
  }, [latestDate]);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const ribbonTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

  return (
    <div className="app-root ed-root">
      {/* —— Ribbon —— */}
      <header className="ribbon">
        <div className="ribbon-l">
          <div className="brand">國<span className="o">際</span>／日報</div>
          <span className="brand-tag">每日策展 · 含遊戲業視角</span>
        </div>
        <div className="ribbon-r">
          <span>{ribbonDate}</span>
          <span className="now">● {ribbonTime} UPDATED</span>
        </div>
      </header>

      {/* —— Filter row —— */}
      <div className="filter-row">
        <div className="filter-cats">
          {[
            { id: "all", label: "全部" },
            { id: "international", label: "國際" },
            { id: "tech", label: "科技" },
            { id: "finance", label: "財經" },
            { id: "games", label: "遊戲業" },
          ].map((c) => (
            <button
              key={c.id}
              className={`pill ${cat === c.id ? "active" : ""}`}
              onClick={() => setCat(c.id)}
            >
              {c.id !== "all" && <span className="dot" style={{ background: CAT_COLOR[c.id] }}></span>}
              {c.label}
              <span className="pill-num">{catCounts[c.id]}</span>
            </button>
          ))}
        </div>
        <div className="filter-dates">
          {dates.map((d) => (
            <button
              key={d}
              className={`date-pill ${date === d ? "active" : ""}`}
              onClick={() => setDate(d)}
            >
              {dateLabel(d)}
            </button>
          ))}
        </div>
      </div>

      {/* —— Empty state —— */}
      {!filtered.length && (
        <div className="empty">
          <p className="empty-mark">·</p>
          <p>此日期 ／ 分類沒有新聞</p>
        </div>
      )}

      {/* —— Hero row —— */}
      {(heroA || critB) && (
        <div className="hero-row">
          {heroA && <HeroTile a={heroA} />}
          {critB && <CritTile a={critB} />}
        </div>
      )}

      {/* —— Section: normal stories (with extra criticals interleaved) —— */}
      {mixed.length > 0 && (
        <>
          <div className="section-bar">
            <span className="section-label">今日要聞</span>
            <span className="section-line"></span>
            <span className="section-count">{String(mixed.length).padStart(2, "0")} 則</span>
          </div>
          <div className="normal-grid">
            {mixed.map(({ a, tone, wide }) => (
              <NormalTile a={a} tone={tone} wide={wide} key={a.url} />
            ))}
          </div>
        </>
      )}

      {/* —— Section: background —— */}
      {background.length > 0 && (
        <>
          <div className="section-bar">
            <span className="section-label">背景閱讀</span>
            <span className="section-line"></span>
            <span className="section-count">{String(background.length).padStart(2, "0")} 則</span>
          </div>
          <div className="bg-grid">
            {background.map((a) => <BgTile a={a} key={a.url} />)}
          </div>
        </>
      )}

      {/* —— Footer —— */}
      <footer className="foot">
        <span>國際／日報 · {dateLabelLong(date)}</span>
        <span>來源：Reuters · BBC · Al Jazeera · TechCrunch · The Verge · IGN · GamesIndustry.biz 等</span>
        <span>已過濾紅媒 · 每日精選 40 則 · 保留 7 日</span>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

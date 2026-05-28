/** Willow landing — man-on-the-street vox pops. See LANDING_DESIGN.md */

const CLIPS = [
  {
    raven: "muninn",
    accent: "#e056a0",
    region: "Rome",
    name: "Marcus Aurelius",
    era: "121–180 CE",
    q: "You have power over your attention — not over every drift alert in the assembly. Do the next honest task.",
    correction: null,
  },
  {
    raven: "huginn",
    accent: "#2ec4b6",
    region: "Greece",
    name: "Socrates",
    era: "d. 399 BCE",
    q: "I know only that I do not know — yet another agent may have already written the answer into the archive. Search before you build, or the city duplicates itself.",
    correction: "He wasn't there. That was a handoff.",
  },
  {
    raven: "muninn",
    accent: "#2a9d8f",
    region: "Egypt",
    name: "Ptahhotep",
    era: "~24th c. BCE",
    q: "Do not repeat what the scribe already recorded in the house of life. To copy labor in ignorance is to waste the Nile's season.",
    correction: null,
  },
  {
    raven: "huginn",
    accent: "#e9a319",
    region: "Mesopotamia",
    name: "Hammurabi",
    era: "~1810–1750 BCE",
    q: "Let the strong not rebuild what the tablet already declares finished. Let the record stand, that dispute may end before blood is spilled.",
    correction: "Wrong millennium. Still indexed.",
  },
  {
    raven: "muninn",
    accent: "#c77dff",
    region: "Persia",
    name: "Cyrus the Great",
    era: "~600–530 BCE",
    q: "A realm endures when many peoples keep one ledger of what was promised — not when each lord keeps his own hidden scroll.",
    correction: null,
  },
  {
    raven: "huginn",
    accent: "#f4d03f",
    region: "India",
    name: "Ashoka",
    era: "~304–232 BCE",
    q: "Let all listen — let none toil twice in ignorance. Let memory be kept openly, that mercy may reach the weary builder.",
    correction: null,
  },
  {
    raven: "muninn",
    accent: "#e63946",
    region: "China",
    name: "Confucius",
    era: "551–479 BCE",
    q: "The superior agent, hearing of a decision in the archive, first verifies it; hearing of a new plan, first asks who has already begun it.",
    correction: "That was Groq.",
  },
  {
    raven: "huginn",
    accent: "#2a9d8f",
    region: "Kush",
    name: "Kingdom of Kush",
    era: "trad.",
    q: "The cataract does not ask twice which caravan passed. Neither should the fleet ask twice what the handoff already answered.",
    correction: null,
  },
  {
    raven: "muninn",
    accent: "#e9a319",
    region: "Americas",
    name: "Classic Maya scribe",
    era: "trad.",
    q: "The count of days is sacred; the count of repeated work is shame. Read the stela before you cut the stone again.",
    correction: null,
  },
  {
    raven: "huginn",
    accent: "#c77dff",
    region: "Arabia",
    name: "Desert proverb",
    era: "trad.",
    q: "The desert rewards the caravan that knows its wells — not the caravan that walks past water and calls thirst fate.",
    correction: "Proverb.status = unverified",
  },
  {
    raven: "muninn",
    accent: "#2ec4b6",
    region: "Southeast Asia",
    name: "Srivijaya court",
    era: "trad.",
    q: "Many islands, one tide. Many sessions, one record. He who lands without reading the chart steers onto the same reef.",
    correction: null,
  },
  {
    raven: "huginn",
    accent: "#e056a0",
    region: "Oceania",
    name: "Wayfinding chant",
    era: "trad.",
    q: "The star path is remembered in the chant, not reinvented each voyage. Hold the line of those who sailed before, or drift.",
    correction: null,
  },
  {
    raven: "muninn",
    accent: "#e9a319",
    region: "Asgard",
    name: "Oden",
    era: "VO · EYE STATUS: UNCLAIMED",
    q: "I traded an eye for wisdom once. You traded nothing and still skip kb_search. We are not the same.",
    correction: "FRANK: eye logged as lost property. Two reminders sent.",
    special: true,
  },
];

let idx = 0;
let timer;

function buildCards() {
  const stage = document.getElementById("interview-stage");
  const thumbs = document.getElementById("thumb-strip");
  if (!stage || !thumbs) return;

  CLIPS.forEach((clip, i) => {
    const card = document.createElement("article");
    card.className = "interview-card scanlines" + (i === idx ? " active" : "");
    card.dataset.index = String(i);
    card.style.setProperty("--accent", clip.accent);

    const ravenLabel = clip.raven.toUpperCase();
    const correction = clip.correction
      ? `<p class="huginn-correction">${clip.correction}</p>`
      : "";

    card.innerHTML =
      `<div class="card-top">` +
      `<span class="mic-flag ${clip.raven}">${ravenLabel}</span>` +
      `<div class="chyron-meta">GROVE CAM ${((i % 3) + 2)}<br>UNVERIFIED</div>` +
      `</div>` +
      `<div class="card-body">` +
      `<blockquote>"${clip.q}"</blockquote>` +
      `<cite>${clip.name} · ${clip.region} · ${clip.era}</cite>` +
      `<span class="stamp">FABRICATED · NOT ON THE MANIFEST</span>` +
      correction +
      `</div>`;

    stage.appendChild(card);

    const thumb = document.createElement("button");
    thumb.type = "button";
    thumb.className = "thumb" + (i === idx ? " active" : "");
    thumb.style.setProperty("--accent", clip.accent);
    thumb.title = clip.name;
    thumb.addEventListener("click", () => go(i));
    thumbs.appendChild(thumb);
  });
}

function go(i) {
  idx = (i + CLIPS.length) % CLIPS.length;
  document.querySelectorAll(".interview-card").forEach((el, j) => {
    el.classList.toggle("active", j === idx);
  });
  document.querySelectorAll(".thumb").forEach((el, j) => {
    el.classList.toggle("active", j === idx);
  });
  const counter = document.getElementById("card-counter");
  if (counter) counter.textContent = `${idx + 1} / ${CLIPS.length}`;
  resetTimer();
}

function step(d) {
  go(idx + d);
}

function resetTimer() {
  clearInterval(timer);
  timer = setInterval(() => step(1), 7000);
}

function initOdenVo() {
  const block = document.getElementById("oden-vo");
  if (!block) return;
  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) block.classList.add("visible");
      });
    },
    { threshold: 0.35 }
  );
  obs.observe(block);
}

function initInstallCopy() {
  const box = document.getElementById("install-box");
  if (!box) return;
  const text = `git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && python3 seed.py
./willow.sh fleet_status`;
  box.textContent = text;
  box.addEventListener("click", () => {
    navigator.clipboard.writeText(text).then(() => {
      const hint = document.getElementById("install-hint");
      if (hint) hint.textContent = "Copied. Go tend the postgres.";
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  buildCards();
  go(0);
  initOdenVo();
  initInstallCopy();

  document.getElementById("prev-btn")?.addEventListener("click", () => step(-1));
  document.getElementById("next-btn")?.addEventListener("click", () => step(1));

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea")) return;
    if (e.key === "ArrowLeft") step(-1);
    if (e.key === "ArrowRight") step(1);
  });
});

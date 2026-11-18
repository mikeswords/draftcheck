"use strict";

const $ = (id) => document.getElementById(id);
const draft = $("draft");
const form = $("review-form");
const checkButton = $("check-button");
const clearButton = $("clear-button");
const copyReview = $("copy-review");
const guide = $("guide");
const signals = {
  lower: "Lower AI signal",
  uncertain: "Uncertain signal",
  higher: "Higher AI signal",
};
const example = [
  "Last Saturday, the library set up a repair café in the meeting room. Volunteers brought sewing kits, pliers, and a toolbox full of spare parts. By noon they had patched four pairs of jeans, straightened a bent bike pedal, and figured out why the coffee grinder from the staff kitchen kept jamming.",
  "It is worth noting that some people stayed after their repairs were finished. One person who came in for a loose chair leg ended up helping another visitor replace the zipper on a backpack. Next month, the library plans to put out a sign-up sheet for anyone who wants to share a repair skill.",
].join("\n\n");

let busy = false;
let lastReview = null;
let voiceProfile = null;

function announce(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").dataset.error = String(error);
}

function updateControls() {
  const words = (draft.value.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu) || []).length;
  $("word-count").textContent = words === 1 ? "1 word" : words + " words";
  checkButton.disabled = !draft.value.trim() || busy;
  clearButton.disabled = !draft.value;
}

function noteElements(notes) {
  return notes.map((note) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    const detail = document.createElement("p");
    title.textContent = note.title;
    detail.textContent = note.detail;
    detail.className = "small-text";
    item.append(title, detail);
    return item;
  });
}

function renderReview(review) {
  const result = review?.detector;
  $("score-wrap").dataset.signal = result?.signal || "empty";
  $("score").textContent = result?.score == null ? "···" : String(result.score);
  $("signal").textContent = review ? signals[result.signal] || "No AI score" : "Awaiting draft";
  $("score-meter").value = result?.score ?? 0;
  $("score-meter").setAttribute("aria-hidden", String(result?.score == null));
  $("detector-note").textContent = result?.note || (
    review ? "Score out of 100 from the local English text model." :
      "AI screening starts at 50 words. Shorter drafts still get writing feedback."
  );

  const passages = result?.passages || [];
  $("passages").hidden = passages.length === 0;
  $("passages").open = false;
  $("passage-list").replaceChildren(...passages.map((part) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = part.score + " / 100";
    const excerpt = document.createElement("p");
    excerpt.className = "small-text";
    excerpt.textContent = part.excerpt;
    item.append(title, excerpt);
    return item;
  }));

  const notes = review?.voice_notes || [];
  $("voice-notes").hidden = notes.length === 0;
  $("voice-notes").replaceChildren(...noteElements(notes));
  $("voice-placeholder").hidden = notes.length > 0;
  $("voice-placeholder").textContent = review ?
    "No stock phrases or long sentences flagged in this draft." :
    "Look for stock phrases and long sentences you could simplify.";
  copyReview.hidden = !review;
}

function draftChanged() {
  if (lastReview) {
    lastReview = null;
    renderReview(null);
    announce("Draft changed. Check it again when you’re ready.");
  } else if (!busy) {
    announce("");
  }
  updateControls();
}

async function runReview(event) {
  event.preventDefault();
  const text = draft.value.trim();
  if (busy || !text) return;

  busy = true;
  form.setAttribute("aria-busy", "true");
  checkButton.firstChild.textContent = "Checking… ";
  updateControls();
  announce("Reviewing on this device…");

  try {
    const response = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const review = await response.json();
    if (!response.ok) throw new Error(review.error || "Draftcheck couldn’t finish this review.");
    if (draft.value.trim() !== text) {
      announce("Draft changed during review. Check the current version when you’re ready.");
      return;
    }

    lastReview = review;
    renderReview(review);
    announce("Review complete.");
  } catch (error) {
    lastReview = null;
    renderReview(null);
    announce(error.message, true);
  } finally {
    busy = false;
    form.removeAttribute("aria-busy");
    checkButton.firstChild.textContent = "Check draft ";
    updateControls();
  }
}

async function showLocalGuide() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) return;
    const status = await response.json();
    $("open-guide").hidden = !status.has_voice_guide;
  } catch {
    // The optional guide button stays hidden if the local server is unavailable.
  }
}

async function openGuide() {
  $("guide-status").textContent = "";
  guide.showModal();
  if (voiceProfile) return;
  try {
    const response = await fetch("/api/profile");
    if (!response.ok) throw new Error();
    voiceProfile = await response.json();
    $("guide-title").textContent = voiceProfile.name;
    $("guide-summary").textContent = voiceProfile.summary;
    $("guide-traits").replaceChildren(...noteElements(voiceProfile.traits));
    $("guide-basis").textContent = voiceProfile.basis;
    $("copy-guide").disabled = false;
  } catch {
    $("guide-summary").textContent = "The local voice guide couldn’t load. Reopen it to try again.";
  }
}

async function copyText(contents, report) {
  try {
    await navigator.clipboard.writeText(contents);
    report("Copied.");
  } catch {
    report("Clipboard unavailable.", true);
  }
}

draft.addEventListener("input", draftChanged);
form.addEventListener("submit", runReview);
$("open-guide").addEventListener("click", openGuide);
$("clear-button").addEventListener("click", () => {
  draft.value = "";
  draftChanged();
  draft.focus();
});
$("example-button").addEventListener("click", () => {
  draft.value = example;
  draft.setSelectionRange(0, 0);
  draft.scrollTop = 0;
  draftChanged();
  draft.focus();
});
form.addEventListener("keydown", (event) => {
  if (!event.isComposing && (event.metaKey || event.ctrlKey) && event.key === "Enter" && !checkButton.disabled) {
    event.preventDefault();
    form.requestSubmit(checkButton);
  }
});
$("copy-guide").addEventListener("click", () => {
  if (!voiceProfile) return;
  const traits = voiceProfile.traits.map((trait) => "- " + trait.title + ". " + trait.detail);
  const guideText = [voiceProfile.chat_instructions, voiceProfile.summary, ...traits].join("\n");
  copyText(guideText, (message) => { $("guide-status").textContent = message; });
});
copyReview.addEventListener("click", () => {
  if (!lastReview) return;
  const { detector, voice_notes: notes } = lastReview;
  const score = detector.score === null ? detector.note :
    "Local Ettin model score " + detector.score + "/100. Use it as a rough signal.";
  const items = notes.map((note) => "- " + note.title + ". " + note.detail);
  copyText([
    "Review the draft with these writing notes. Keep its purpose, tone, and factual claims intact. Suggest specific wording changes where they improve clarity.",
    score,
    ...items,
  ].join("\n"), announce);
});

if (!navigator.platform.toLowerCase().includes("mac")) $("modifier").textContent = "Ctrl";
updateControls();
renderReview(null);
showLocalGuide();

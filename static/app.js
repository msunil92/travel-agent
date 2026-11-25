const form = document.querySelector("#travel-form");
const questionField = document.querySelector("#question");
const submitButton = document.querySelector("#submit-button");
const responseSection = document.querySelector("#response-section");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const answerCard = document.querySelector("#answer-card");

/**
 * Append supported inline Markdown as safe DOM nodes.
 * @param {Node} parent Element that receives the generated inline content.
 * @param {string} text Text containing emphasis, code, or HTTP(S) links.
 */
function appendInlineMarkdown(parent, text) {
  const pattern = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g;
  let cursor = 0;

  for (const match of text.matchAll(pattern)) {
    const token = match[0];
    const start = match.index;
    parent.append(document.createTextNode(text.slice(cursor, start)));

    let element;
    let content;
    if (token.startsWith("**") || token.startsWith("__")) {
      element = document.createElement("strong");
      content = token.slice(2, -2);
    } else if (token.startsWith("*") || token.startsWith("_")) {
      element = document.createElement("em");
      content = token.slice(1, -1);
    } else if (token.startsWith("`")) {
      element = document.createElement("code");
      content = token.slice(1, -1);
    } else {
      const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
      element = document.createElement("a");
      element.href = link[2];
      element.target = "_blank";
      element.rel = "noopener noreferrer";
      content = link[1];
    }

    element.textContent = content;
    parent.append(element);
    cursor = start + token.length;
  }

  parent.append(document.createTextNode(text.slice(cursor)));
}

/**
 * Convert flattened or multiline pipe tables into readable Markdown lists.
 * @param {string} markdown Raw model response.
 * @returns {string} Markdown with recognized tables expanded into labeled rows.
 */
function formatPipeTables(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const formatted = [];

  for (let index = 0; index < lines.length;) {
    if (!lines[index].includes("|")) {
      formatted.push(lines[index]);
      index += 1;
      continue;
    }

    const tableLines = [];
    while (index < lines.length && lines[index].includes("|")) {
      tableLines.push(lines[index]);
      index += 1;
    }

    const cells = tableLines
      .join(" ")
      .split("|")
      .map((cell) => cell.trim())
      .filter(Boolean);
    const separatorIndex = cells.findIndex((cell) => /^:?-{3,}:?$/.test(cell));
    if (separatorIndex < 1) {
      formatted.push(...tableLines);
      continue;
    }

    const columnCount = separatorIndex;
    const headers = cells.slice(0, columnCount);
    const rows = [];
    for (let cellIndex = separatorIndex + columnCount; cellIndex + columnCount <= cells.length; cellIndex += columnCount) {
      rows.push(cells.slice(cellIndex, cellIndex + columnCount));
    }

    if (!rows.length) {
      formatted.push(...tableLines);
      continue;
    }

    const dayIndex = headers.findIndex((header) => /\bday\b/i.test(header));
    const baseIndex = headers.findIndex((header) => /\b(base|island|place|location)\b/i.test(header));
    const itemIndex = headers.findIndex((header) => /\b(item|category|expense)\b/i.test(header));
    const costIndex = headers.findIndex((header) => /\b(cost|price|amount|fare|estimate)\b/i.test(header));
    for (const row of rows) {
      if (dayIndex >= 0) {
        const day = row[dayIndex].replace(/^day\s*/i, "");
        const place = baseIndex >= 0 ? ` — ${row[baseIndex]}` : "";
        formatted.push(`### Day ${day}${place}`);
        const fields = row
          .map((value, fieldIndex) => ({ value, header: headers[fieldIndex] }))
          .filter((_, fieldIndex) => fieldIndex !== dayIndex && fieldIndex !== baseIndex);
        for (const field of fields) {
          formatted.push(`- **${field.header}:** ${field.value}`);
        }
      } else if (itemIndex >= 0 && costIndex >= 0) {
        const label = row[itemIndex].replace(/\*\*/g, "").trim();
        formatted.push(`- **${label}:** ${row[costIndex]}`);
      } else {
        formatted.push(`- ${row.map((value, fieldIndex) => `**${headers[fieldIndex]}:** ${value}`).join(" · ")}`);
      }
    }
  }

  return formatted.join("\n");
}

/**
 * Render headings, lists, and inline formatting without injecting raw HTML.
 * @param {string} markdown Markdown response returned by the travel API.
 */
function renderAnswer(markdown) {
  const answer = document.querySelector("#answer");
  answer.replaceChildren();

  let paragraph = [];
  let list = null;
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const element = document.createElement("p");
    appendInlineMarkdown(element, paragraph.join(" "));
    answer.append(element);
    paragraph = [];
  };
  const flushList = () => {
    list = null;
  };

  for (const line of formatPipeTables(markdown).split("\n")) {
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const item = line.match(/^\s*(?:[-*+]|\d+[.)])\s+(.+)$/);

    if (heading) {
      flushParagraph();
      flushList();
      const element = document.createElement(heading[1].length === 1 ? "h3" : "h4");
      appendInlineMarkdown(element, heading[2]);
      answer.append(element);
    } else if (item) {
      flushParagraph();
      const ordered = /^\s*\d/.test(line);
      const tag = ordered ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== tag) {
        flushList();
        list = document.createElement(tag);
        answer.append(list);
      }
      const element = document.createElement("li");
      appendInlineMarkdown(element, item[1]);
      list.append(element);
    } else if (!line.trim()) {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line.trim());
    }
  }

  flushParagraph();
}

/**
 * Show the requested API response state and hide the other states.
 * @param {"loading"|"error"|"answer"} state State to display.
 */
function showState(state) {
  responseSection.hidden = false;
  loadingState.hidden = state !== "loading";
  errorState.hidden = state !== "error";
  answerCard.hidden = state !== "answer";
}

/**
 * Populate the final answer and expandable research panels from the API payload.
 * @param {Object} data Response object returned by `/api/ask`.
 */
function fillDetails(data) {
  renderAnswer(data.answer || "No answer was returned.");

  const sections = [
    ["flight-details", "flight-results", data.flight_results],
    ["hotel-details", "hotel-results", data.hotel_results],
    ["itinerary-details", "itinerary", data.itinerary],
  ];

  for (const [detailsId, contentId, content] of sections) {
    const details = document.getElementById(detailsId);
    document.getElementById(contentId).textContent = content || "No details available.";
    details.hidden = !content;
    details.open = false;
  }
}

/**
 * Submit the user's question and display the resulting plan or an error.
 * @param {SubmitEvent} event Form submit event.
 */
async function handleQuestionSubmit(event) {
  event.preventDefault();
  const question = questionField.value.trim();

  if (question.length < 3) {
    questionField.focus();
    return;
  }

  submitButton.disabled = true;
  showState("loading");

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "We couldn’t plan your trip. Please try again.");
    }

    fillDetails(data);
    showState("answer");
    answerCard.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    errorState.textContent = error.message || "Something went wrong. Please try again.";
    showState("error");
  } finally {
    submitButton.disabled = false;
  }
}

/**
 * Copy an example request into the question field for editing or submission.
 * @param {HTMLButtonElement} button Clicked example prompt.
 */
function handleSuggestionClick(button) {
  questionField.value = button.textContent;
  questionField.focus();
}

/**
 * Clear the current plan and return focus to the question field.
 */
function handleNewPlanClick() {
  form.reset();
  responseSection.hidden = true;
  questionField.focus();
}

form.addEventListener("submit", handleQuestionSubmit);
document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => handleSuggestionClick(button));
});
document.querySelector("#new-plan-button").addEventListener("click", handleNewPlanClick);

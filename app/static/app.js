/**
 * app/static/app.js
 *
 * Frontend logic for the single-page UI: theme toggle (persisted in
 * localStorage), the call to POST /ask, and rendering the response (SQL,
 * attempt count, results table). Showing readable errors is step 7.
 */

const THEME_KEY = "theme";
const themeToggle = document.getElementById("theme-toggle");
const questionForm = document.getElementById("question-form");
const questionInput = document.getElementById("question-input");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");
const statusText = document.getElementById("status-text");
const sqlSection = document.getElementById("sql-section");
const sqlOutput = document.getElementById("sql-output");
const attemptsEl = document.getElementById("attempts");
const resultsSection = document.getElementById("results-section");
const rowCountEl = document.getElementById("row-count");
const resultsTable = document.getElementById("results-table");
const resultsHead = resultsTable.querySelector("thead");
const resultsBody = resultsTable.querySelector("tbody");

/** Applies a theme and updates the toggle label (it shows the mode you switch TO). */
function applyTheme(theme) {
  const isLight = theme === "light";
  document.body.classList.toggle("light-mode", isLight);
  themeToggle.textContent = isLight ? "DARK" : "LIGHT";
}

/** Reads the saved theme. Storage can be blocked, so never assume it works. */
function loadSavedTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Not critical: the theme just won't persist between visits.
  }
}

themeToggle.addEventListener("click", () => {
  const next = document.body.classList.contains("light-mode") ? "dark" : "light";
  applyTheme(next);
  saveTheme(next);
});

applyTheme(loadSavedTheme());

/**
 * Shows/hides the loading indicator and disables the form while a request
 * is in flight. Also hides the previous answer's SQL and results panels
 * when a new request starts, so they don't stay on screen next to the
 * "loading" state while the new question is still processing.
 */
function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  questionInput.disabled = isLoading;
  statusBox.hidden = !isLoading;
  if (isLoading) {
    statusText.textContent = "Thinking... this can take up to a minute on the first request.";
    sqlSection.hidden = true;
    resultsSection.hidden = true;
  }
}

/** Shows the generated SQL and attempt count, and reveals the panel. */
function showSql(sql, attempts) {
  sqlOutput.textContent = sql;
  attemptsEl.textContent = attempts === 1 ? "1 attempt" : `${attempts} attempts`;
  sqlSection.hidden = false;
}

/**
 * Renders the query result as a table and reveals the panel.
 * Rebuilds <thead> from `columns` on every call rather than assuming a
 * fixed header, so it stays correct if the dataset's columns ever change.
 * Cells use textContent only (never innerHTML): column values come from
 * the CSV and could contain HTML that must not be executed. Clearing the
 * containers below with innerHTML = "" is safe — that's a fixed string we
 * write, not data from the CSV.
 */
function showResults(columns, rows) {
  resultsHead.innerHTML = "";
  resultsBody.innerHTML = "";

  const headRow = document.createElement("tr");
  for (const column of columns) {
    const th = document.createElement("th");
    th.textContent = column;
    headRow.appendChild(th);
  }
  resultsHead.appendChild(headRow);

  if (rows.length === 0) {
    const emptyRow = document.createElement("tr");
    const emptyCell = document.createElement("td");
    emptyCell.textContent = "No results for this query.";
    emptyCell.colSpan = columns.length;
    emptyRow.appendChild(emptyCell);
    resultsBody.appendChild(emptyRow);
  } else {
    for (const row of rows) {
      const tr = document.createElement("tr");
      for (const value of row) {
        const td = document.createElement("td");
        td.textContent = value === null ? "—" : value;
        tr.appendChild(td);
      }
      resultsBody.appendChild(tr);
    }
  }

  rowCountEl.textContent = rows.length === 1 ? "1 row" : `${rows.length} rows`;
  resultsSection.hidden = false;
}

/**
 * Sends the question to POST /ask and logs the result.
 * Error shape from the backend varies: a string (custom errors, e.g. 422
 * "retries exhausted" or 504 timeout) or a list of objects (FastAPI's own
 * Pydantic validation 422, e.g. empty body). Both are just logged for now;
 * showing them to the user is a later step (7).
 */
async function handleSubmit(event) {
  event.preventDefault();

  const question = questionInput.value.trim();
  if (!question) return;

  setLoading(true);

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Ask failed:", response.status, data.detail);
      return;
    }

    console.log("Ask succeeded:", data);
    showSql(data.sql, data.attempts);
    showResults(data.columns, data.rows);
  } catch (err) {
    // Network failure: server down, no connection, etc. — not an HTTP error response.
    console.error("Network error calling /ask:", err);
  } finally {
    setLoading(false);
  }
}

questionForm.addEventListener("submit", handleSubmit);

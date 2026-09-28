/**
 * app/static/app.js
 *
 * Frontend logic for the single-page UI: theme toggle (persisted in
 * localStorage) and the call to POST /ask, which sends the user's question
 * and receives the generated SQL, the query results and the retry count
 * from the backend (app/main.py). Loading state is shown while the request
 * is in flight; showing the SQL and results table on screen is a later step.
 */

const THEME_KEY = "theme";
const themeToggle = document.getElementById("theme-toggle");
const questionForm = document.getElementById("question-form");
const questionInput = document.getElementById("question-input");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");
const statusText = document.getElementById("status-text");

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

/** Shows/hides the loading indicator and disables the form while a request is in flight. */
function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  questionInput.disabled = isLoading;
  statusBox.hidden = !isLoading;
  if (isLoading) {
    statusText.textContent = "Thinking... this can take up to a minute on the first request.";
  }
}

/**
 * Sends the question to POST /ask and logs the result.
 * Error shape from the backend varies: a string (custom errors, e.g. 422
 * "retries exhausted" or 504 timeout) or a list of objects (FastAPI's own
 * Pydantic validation 422, e.g. empty body). Both are just logged for now;
 * showing them to the user is a later step.
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
  } catch (err) {
    // Network failure: server down, no connection, etc. — not an HTTP error response.
    console.error("Network error calling /ask:", err);
  } finally {
    setLoading(false);
  }
}

questionForm.addEventListener("submit", handleSubmit);
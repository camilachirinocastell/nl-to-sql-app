/**
 * app/static/app.js
 *
 * Step 2 scope: theme toggle only. The fetch to POST /ask, the loading
 * state, the SQL block, the results table and error handling are added in
 * the next steps.
 */

const THEME_KEY = "theme";
const themeToggle = document.getElementById("theme-toggle");

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

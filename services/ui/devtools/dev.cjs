const path = require("path");
const fs = require("fs");
const concurrently = require("concurrently");

const isWin = process.platform === "win32";
const cwd = process.cwd();

// --- 1️⃣ Locate the Python binary from the virtual environment (fallback to system Python) ---
const venvPython = isWin
  ? path.join(cwd, ".venv", "Scripts", "python.exe")
  : path.join(cwd, ".venv", "bin", "python");

let pythonCmd;

// Prefer the venv Python if available
if (fs.existsSync(venvPython)) {
  pythonCmd = `"${venvPython}"`;
  console.log(`✅ Using Python from venv: ${venvPython}`);
} else {
  // Fallback to system Python depending on OS
  pythonCmd = isWin ? "py" : "python3";
  console.log(`⚠️ No .venv found, using system Python: ${pythonCmd}`);
}

// --- 2️⃣ Commands to run in parallel ---
const cssCmd = `tailwindcss -i ./src/input.css -o ./static/css/app.css --watch`; // Tailwind in watch mode
const apiCmd = `${pythonCmd} -m devtools.dev_server`; // Starts your Python dev server with livereload

// --- 3️⃣ Run the tasks concurrently ---
concurrently(
  [
    { command: cssCmd, name: "CSS" }, // CSS build pipeline
    { command: apiCmd, name: "API" }, // Backend dev server
  ],
  {
    prefix: "{name}",                       // Prefix logs by task name
    killOthersOn: ["failure", "success"],   // Stop the other task on exit of one
    restartTries: 0,                        // Do not auto-restart tasks
  }
).result
  .then(() => process.exit(0))
  .catch(() => process.exit(1));

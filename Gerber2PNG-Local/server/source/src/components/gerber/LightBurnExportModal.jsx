import { useEffect, useState } from "react";
import PropTypes from "prop-types";
import { ArrowTopRightOnSquareIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { motion } from "motion/react";

const ORIGINS = [
  ["top-left", "Top left"],
  ["top-center", "Top center"],
  ["top-right", "Top right"],
  ["middle-left", "Middle left"],
  ["center", "Center"],
  ["middle-right", "Middle right"],
  ["bottom-left", "Bottom left"],
  ["bottom-center", "Bottom center"],
  ["bottom-right", "Bottom right"],
];

const getPngFilename = (name) => `${name || "gerber-export"}_1000dpi.png`.replace(/[^A-Za-z0-9._-]/g, "_");

const postJson = async (path, body) => {
  const response = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Local server returned ${response.status}.`);
  return result;
};

export default function LightBurnExportModal({ png, onClose }) {
  const [positionX, setPositionX] = useState("75.5");
  const [positionY, setPositionY] = useState("50");
  const [origin, setOrigin] = useState("center");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/lightburn/status")
      .then((response) => response.json())
      .then((result) => { if (active) setConnected(Boolean(result.connected)); })
      .catch(() => { if (active) setError("Start the Gerber2PNG local server, then reopen this dialog."); });
    return () => { active = false; };
  }, []);

  const pairLightBurn = async () => {
    setBusy(true);
    setError("");
    setMessage("Approve the Gerber2PNG connection request in LightBurn.");
    try {
      await postJson("/api/lightburn/connect");
      setConnected(true);
      setMessage("Connected to LightBurn. Choose a position and import this PNG.");
    } catch (connectionError) {
      setMessage("");
      setError(connectionError.message);
    } finally {
      setBusy(false);
    }
  };

  const sendToLightBurn = async (event) => {
    event.preventDefault();
    if (!Number.isFinite(Number(positionX)) || !Number.isFinite(Number(positionY))) {
      setError("Enter valid X and Y coordinates in millimeters.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("Sending PNG to LightBurn…");
    try {
      const image = await fetch(png.url);
      const blob = await image.blob();
      const response = await fetch("/api/lightburn/upload", {
        method: "POST",
        headers: {
          "Content-Type": "image/png",
          "X-Filename": getPngFilename(png.name),
          "X-Position-X": String(Number(positionX)),
          "X-Position-Y": String(Number(positionY)),
          "X-Origin": origin,
        },
        body: blob,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || `LightBurn import failed (${response.status}).`);
      setMessage(`LightBurn accepted ${result.filename || png.name}. The import is processing.`);
    } catch (uploadError) {
      setMessage("");
      setError(uploadError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-[2px] dark:bg-slate-950/75"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose(); }}
    >
      <motion.div
        role="dialog" aria-modal="true" aria-labelledby="lightburn-export-title"
        className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        initial={{ y: 8, scale: 0.98, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: 8, scale: 0.98, opacity: 0 }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="lightburn-export-title" className="text-sm font-semibold text-slate-900 dark:text-white">Send PNG to LightBurn</h2>
            <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{getPngFilename(png.name)} · {png.width} × {png.height} mm</p>
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40 dark:hover:bg-slate-800"><XMarkIcon className="h-5 w-5" /></button>
        </div>

        {!connected ? (
          <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-300">
            <p>Connect once per local server session. If LightBurn is closed, Gerber2PNG will launch it. Approve the upload permission when prompted.</p>
            <button type="button" onClick={pairLightBurn} disabled={busy} className="w-full rounded-lg bg-emerald-600 px-3 py-2 font-semibold text-white hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60">{busy ? "Waiting for LightBurn…" : "Connect to LightBurn"}</button>
          </div>
        ) : (
          <form onSubmit={sendToLightBurn} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1 text-xs font-medium text-slate-700 dark:text-slate-200">Anchor X <span className="font-normal text-slate-500">(mm)</span>
                <input type="number" step="any" value={positionX} onChange={(event) => setPositionX(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950" />
              </label>
              <label className="space-y-1 text-xs font-medium text-slate-700 dark:text-slate-200">Anchor Y <span className="font-normal text-slate-500">(mm)</span>
                <input type="number" step="any" value={positionY} onChange={(event) => setPositionY(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950" />
              </label>
            </div>
            <label className="block space-y-1 text-xs font-medium text-slate-700 dark:text-slate-200">Point placed at X/Y
              <select value={origin} onChange={(event) => setOrigin(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950">
                {ORIGINS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">LightBurn places the selected point of the PNG’s bounding box at these workspace coordinates. Importing adds the image to the current project.</p>
            <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60"><ArrowTopRightOnSquareIcon className="h-4 w-4" />{busy ? "Sending…" : "Import into LightBurn"}</button>
          </form>
        )}

        {(message || error) && <p role={error ? "alert" : "status"} className={`rounded-lg px-3 py-2 text-xs ${error ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"}`}>{error || message}</p>}
      </motion.div>
    </motion.div>
  );
}

LightBurnExportModal.propTypes = {
  png: PropTypes.shape({
    name: PropTypes.string.isRequired,
    url: PropTypes.string.isRequired,
    width: PropTypes.number,
    height: PropTypes.number,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
};

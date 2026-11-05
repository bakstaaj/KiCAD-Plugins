import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { generateDrillGcode } from "../../utils/gcode/excellonToGcode";
import toast from "react-hot-toast";

const initialSettings = {
  depth: "-2.1",
  safeZ: "3.0",
  toolChangeZ: "25.0",
  plunge: "300",
  spindle: "900",
  dwell: "3",
};

const DrillGcodeModal = ({ open, onClose, boardId, drillFiles, topSvg }) => {
  const [settings, setSettings] = useState(initialSettings);
  if (!open) return null;

  const generate = () => {
    try {
      const outline = topSvg?.querySelector("clipPath path");
      const result = generateDrillGcode(drillFiles, outline, settings);
      const blob = new Blob([result.gcode], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${boardId || "board"}_drill.nc`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success(`Generated ${result.holeCount} holes using ${result.toolCount} drill size${result.toolCount === 1 ? "" : "s"}.`);
      onClose();
    } catch (error) {
      toast.error(error.message || "Could not generate drill G-code.");
    }
  };

  const fields = [
    ["Drill depth (mm, negative)", "depth"],
    ["Safe Z height (mm)", "safeZ"],
    ["Tool change Z height (mm)", "toolChangeZ"],
    ["Plunge feed rate (mm/min)", "plunge"],
    ["Spindle RPM", "spindle"],
    ["Spindle dwell (s)", "dwell"],
  ];

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-[2px] dark:bg-slate-950/70"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
      >
        <motion.div
          role="dialog" aria-modal="true" aria-labelledby="drill-gcode-title"
          className="w-full max-w-lg space-y-4 rounded-xl bg-white p-5 shadow-xl dark:border dark:border-slate-800 dark:bg-slate-900"
          initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
        >
          <div>
            <h2 id="drill-gcode-title" className="text-sm font-semibold text-slate-900 dark:text-slate-100">Export drill G-code (NC)</h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              Top-side orientation. The board outline’s lower-left corner becomes X0 Y0. Drill sizes are sorted smallest to largest, with a manual tool-change pause for each size.
            </p>
          </div>
          <div className="grid grid-cols-[1fr_130px] items-center gap-x-3 gap-y-2">
            {fields.map(([label, key]) => (
              <label key={key} className="contents">
                <span className="text-xs text-slate-700 dark:text-slate-300">{label}</span>
                <input
                  type="number" step="any" value={settings[key]}
                  onChange={(event) => setSettings((previous) => ({ ...previous, [key]: event.target.value }))}
                  className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700">Cancel</button>
            <button onClick={generate} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700">Generate NC file</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default DrillGcodeModal;

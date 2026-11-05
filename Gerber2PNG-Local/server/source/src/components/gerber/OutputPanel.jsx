import { motion, AnimatePresence } from "motion/react";
import {
  ArrowRightEndOnRectangleIcon,
  ArrowDownTrayIcon,
  Cog6ToothIcon,
  FolderArrowDownIcon,
  Squares2X2Icon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import PngCard from "../ui/PngCard";
import { useState } from "react";
import JSZip from "jszip";
import ImageIcon from "../icons/ImageIcon";
import BulkLayoutPanel from "./multiLayout/Panel";
import { useApp } from "../context/AppContext";
import ModsPanel from "./modsPanel/Panel";
import mods from './../../assets/favicon.ico'
import { useGerberLayer, useGerberSettings } from "../context/GerberContext";
import { addTabsToOutlinePng } from "../../utils/svgConverter/svg2png";
import OutlineTabsModal from "./OutlineTabsModal";
import PngPreviewModal from "./PngPreviewModal";
import LightBurnExportModal from "./LightBurnExportModal";
import { createStencilDxf } from "../../utils/dxf/stencilDxf";
import DrillGcodeModal from "./DrillGcodeModal";
import toast from "react-hot-toast";

const OutputPanel = () => {
  const { pngFiles, setPngFiles, outlineTabPreset, setOutlineTabPreset } = useApp();
  const { doubleSide, outlineToolWidth, stackConfig } = useGerberSettings();
  const { topstack, bottomstack, drillFiles } = useGerberLayer();

  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showModsPanel, setShowModsPanel] = useState(false);
  const [selectedPng, setSelectedPng] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [tabEditorPng, setTabEditorPng] = useState(null);
  const [previewPng, setPreviewPng] = useState(null);
  const [lightBurnPng, setLightBurnPng] = useState(null);
  const [showStencilModal, setShowStencilModal] = useState(false);
  const [showDrillGcodeModal, setShowDrillGcodeModal] = useState(false);

  const exportStencilDxf = (side) => {
    const stack = side === "top" ? topstack : bottomstack;
    try {
      const dxf = createStencilDxf(stack?.svg, side, stackConfig);
      const blob = new Blob([dxf], { type: "application/dxf" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${stack?.id || "board"}_${side}-solder-stencil.dxf`;
      link.click();
      URL.revokeObjectURL(url);
      setShowStencilModal(false);
    } catch (error) {
      toast.error(error.message || "Could not generate stencil DXF.");
    }
  };

  const hasFiles = pngFiles.length > 0;

  const handleDeleteAll = () => {
    pngFiles.forEach((item) => {
      URL.revokeObjectURL(item.url);
      if (item.originalUrl) URL.revokeObjectURL(item.originalUrl);
    });
    setPngFiles([]);
    setShowDeleteConfirm(false);
  };

  const downloadZip = () => {
    if (!hasFiles) return;

    const zip = new JSZip();
    Promise.all(
      pngFiles.map((pngBlob, index) => {
        return fetch(pngBlob.url)
          .then((res) => res.blob())
          .then((blob) => {
            zip.file(`${pngBlob.name}_${index}.png`, blob);
          });
      })
    ).then(() => {
      zip.generateAsync({ type: "blob" }).then((zipBlob) => {
        const url = window.URL.createObjectURL(zipBlob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `gerber_files_${pngFiles.length}.zip`;
        link.click();
      });
    });
  };

  const canAddTabsToPng = (png) => {
    if (png.job !== "outline") return false;

    if (doubleSide) {
      return png.directory === "bottomlayer";
    }

    return png.directory === "toplayer";
  };

  const openTabsEditor = (targetUrl) => {
    const targetPng = pngFiles.find((png) => png.url === targetUrl);
    if (!targetPng) return;
    setTabEditorPng(targetPng);
  };

  const handleApplyTabs = async ({ tabWidthMm, tabDepthMm, tabs }) => {
    if (!tabEditorPng) return;
    const targetPng = pngFiles.find((png) => png.url === tabEditorPng.url) || tabEditorPng;
    const hasAnyTabs = Array.isArray(tabs) && tabs.length > 0;

    if (!hasAnyTabs) {
      if (targetPng.hasTabs && targetPng.originalUrl) {
        setPngFiles((prev) =>
          prev.map((png) =>
            png.url === targetPng.url
              ? {
                  ...png,
                  url: png.originalUrl,
                  hasTabs: false,
                  originalUrl: undefined,
                  tabConfig: undefined,
                }
              : png
          )
        );

        URL.revokeObjectURL(targetPng.url);
      } else {
        setPngFiles((prev) =>
          prev.map((png) =>
            png.url === targetPng.url
              ? {
                  ...png,
                  hasTabs: false,
                  tabConfig: undefined,
                }
              : png
          )
        );
      }

      setTabEditorPng(null);
      return;
    }

    if (targetPng.hasTabs && targetPng.originalUrl) {
      URL.revokeObjectURL(targetPng.url);
    }

    try {
      const { url } = await addTabsToOutlinePng(targetPng.originalUrl || targetPng.url, {
        toolWidthMm: parseFloat(outlineToolWidth) || 0.8,
        tabWidthMm,
        tabDepthMm,
        tabs,
      });

      setPngFiles((prev) =>
        prev.map((png) =>
          png.url === targetPng.url
            ? {
                ...png,
                url,
                hasTabs: true,
                originalUrl: png.originalUrl || png.url,
                tabConfig: {
                  tabWidthMm,
                  tabDepthMm,
                  tabs,
                },
              }
            : png
        )
      );
      setTabEditorPng(null);
    } catch (error) {
      console.error("Failed to add tabs to outline PNG", error);
    }
  };

  const handleRemoveTabs = () => {
    if (!tabEditorPng) return;
    const targetPng = pngFiles.find((png) => png.url === tabEditorPng.url) || tabEditorPng;
    if (!targetPng.hasTabs || !targetPng.originalUrl) {
      setTabEditorPng(null);
      return;
    }

    setPngFiles((prev) =>
      prev.map((png) =>
        png.url === targetPng.url
          ? {
              ...png,
              url: png.originalUrl,
              hasTabs: false,
              originalUrl: undefined,
              tabConfig: undefined,
            }
          : png
      )
    );

    URL.revokeObjectURL(targetPng.url);
    setTabEditorPng(null);
  };

  const handleSaveTabPreset = ({ tabWidthMm, tabDepthMm, tabs }) => {
    setOutlineTabPreset({
      tabWidthMm,
      tabDepthMm,
      tabs,
    });
  };

  return (
    <>
      {/* MAIN PANEL */}
      <div className="flex flex-col h-full bg-white border border-slate-200 rounded-xl overflow-hidden transition-colors dark:bg-slate-900 dark:border-slate-800">

        {/* HEADER */}
        <div className="px-3 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
                <div className="flex flex-col">
                    {pngFiles.length > 0 ? (
                    <>
                        {/* READY STATE */}
                        <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 dark:bg-cyan-400" />
                        <p className="text-xs font-semibold text-gray-700 dark:text-slate-100">
                            Ready for Mods
                        </p>
                        </div>

                        <p className="text-[10px] text-gray-500 ml-3 dark:text-slate-400">
                        {pngFiles.length} output
                        {pngFiles.length !== 1 && "s"} generated
                        </p>
                    </>
                    ) : (
                    <>
                        {/* EMPTY STATE */}
                        <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400">
                                No outputs yet
                            </p>
                        </div>

                        <p className="text-[10px] text-gray-400 ml-3 dark:text-slate-500">
                            Generate PNG to continue
                        </p>
                    </>
                    )}
                </div>
            </div>
            <motion.button
                whileTap={{ scale: hasFiles ? 0.95 : 1 }}
                whileHover={hasFiles ? { y: -1 } : {}}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                disabled={!hasFiles || isExporting}
                onClick={() => {
                  setIsExporting(true);
                  setTimeout(() => {
                      setSelectedPng(pngFiles[0]);
                      setShowModsPanel(true);
                      setIsExporting(false);
                  }, 200);
                }}
                className={`
                flex items-center gap-2 px-2 py-2 text-xs font-semibold rounded-xl transition border
                ${
                    hasFiles
                    ? "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-300 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200 dark:hover:bg-emerald-500/15"
                    : "bg-slate-100 border-slate-200 text-gray-400 cursor-not-allowed dark:bg-slate-800 dark:border-slate-700 dark:text-slate-500"
                }
                `}
            >
              <img className="w-5 h-5" src={mods} alt="icon" />
              {isExporting ? "Opening..." : "Open in Mods"}
            </motion.button>
        </div>

        {/* ACTION STRIP */}
        <div className="px-3 py-2 bg-slate-50 dark:bg-slate-900/40">
          <div className="flex items-center justify-between bg-white rounded-xl px-1 py-1 border border-indigo-100 dark:bg-slate-950/50 dark:border-slate-800">

            {/* LEFT */}
            <div className="flex items-center gap-1">
              <motion.button
                whileTap={{ scale: hasFiles ? 0.96 : 1 }}
                disabled={!hasFiles}
                onClick={downloadZip}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition shadow-sm border
                  ${
                    hasFiles
                      ? "bg-gradient-to-r from-[#D3346E] to-[#B81D50] border-[#C12B61] text-white hover:from-[#B81D50] hover:to-[#D3346E]"
                      : "bg-slate-100 border-slate-200 text-gray-400 cursor-not-allowed dark:bg-slate-800 dark:border-slate-700 dark:text-slate-500"
                  }
                `}
              >
                <FolderArrowDownIcon width={14} />
                Download All
              </motion.button>
              <motion.button
                whileTap={{ scale: hasFiles ? 0.96 : 1 }}
                disabled={!hasFiles}
                onClick={() => setShowBulkModal(true)}
                className={`
                  flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-lg transition
                  ${
                    hasFiles
                      ? "text-gray-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      : "text-gray-400 cursor-not-allowed dark:text-slate-500"
                  }
                `}
              >
                <Squares2X2Icon width={14} />
                Layout
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.96 }}
                disabled={!topstack?.svg || !bottomstack?.svg}
                onClick={() => setShowStencilModal(true)}
                title="Export solder-paste apertures and board edge as DXF"
                className={`flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-lg transition ${
                  topstack?.svg && bottomstack?.svg
                    ? "text-gray-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    : "text-gray-400 cursor-not-allowed dark:text-slate-500"
                }`}
              >
                <ArrowDownTrayIcon width={14} />
                Stencil DXF
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.96 }}
                disabled={!drillFiles?.length || !topstack?.svg}
                onClick={() => setShowDrillGcodeModal(true)}
                title={drillFiles?.length ? "Export Excellon drill hits as NC G-code" : "Upload a KiCad Excellon drill file (.drl)"}
                className={`flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-lg transition ${
                  drillFiles?.length && topstack?.svg
                    ? "text-gray-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    : "text-gray-400 cursor-not-allowed dark:text-slate-500"
                }`}
              >
                <Cog6ToothIcon width={14} />
                Drill G-code
              </motion.button>
            </div>

            {/* DELETE */}
            <motion.button
              whileTap={{ scale: hasFiles ? 0.96 : 1 }}
              disabled={!hasFiles}
              onClick={() => setShowDeleteConfirm(true)}
              className={`
                p-2 rounded-lg transition
                ${
                  hasFiles
                    ? "text-red-500 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-500/10"
                    : "text-gray-400 cursor-not-allowed dark:text-slate-500"
                }
              `}
            >
              <TrashIcon width={14} />
            </motion.button>

          </div>
        </div>

        {/* FILE LIST */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-3 space-y-2">
          <AnimatePresence>
            {hasFiles ? (
              pngFiles
                .slice()
                .reverse()
                .map((item, index) => (
                  <motion.div
                    key={item.url}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{
                      duration: 0.18,
                      delay: index * 0.04,
                    }}
                    whileHover={{ y: -1 }}
                    className="rounded-xl transition"
                  >
                    <PngCard
                      blobUrl={item.url}
                      name={`${item.name}_1000dpi.png`}
                      handlePreview={() => setPreviewPng(item)}
                      handleLightBurn={() => setLightBurnPng(item)}
                      handleDelete={() => {
                        if (item.originalUrl) URL.revokeObjectURL(item.originalUrl);
                        setPngFiles((prev) => {
                          const updated = [...prev];
                          updated.splice(
                            pngFiles.length - 1 - index,
                            1
                          );
                          return updated;
                        });
                        URL.revokeObjectURL(item.url);
                      }}
                      handleEditTabs={() => openTabsEditor(item.url)}
                      canAddTabs={canAddTabsToPng(item)}
                      hasTabs={Boolean(item.hasTabs)}
                      handleMods={() => {
                        setSelectedPng(item);
                        setShowModsPanel(true);
                      }}
                    />
                  </motion.div>
                ))
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center h-full text-center gap-3"
              >
                <ImageIcon width={34} height={34} stroke="#9CA3AF" />
                <p className="text-sm text-gray-600">
                  No outputs generated
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* DELETE MODAL */}
      <AnimatePresence>
        {showStencilModal && (
          <motion.div
            className="fixed inset-0 bg-black/30 backdrop-blur-[2px] flex items-center justify-center z-50 dark:bg-slate-950/70"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setShowStencilModal(false)}
          >
            <motion.div
              className="bg-white rounded-xl p-5 w-[340px] space-y-4 shadow-xl dark:bg-slate-900 dark:border dark:border-slate-800"
              initial={{ scale: 0.94, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.94, opacity: 0 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-slate-100">Export solder stencil DXF</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Choose the board side. The file contains solder-paste apertures and the board edge in millimeters.</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => exportStencilDxf("top")} className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Top side</button>
                <button onClick={() => exportStencilDxf("bottom")} className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Bottom side</button>
              </div>
              <div className="flex justify-end">
                <button onClick={() => setShowStencilModal(false)} className="px-3 py-1.5 text-xs rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700">Cancel</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <DrillGcodeModal
        open={showDrillGcodeModal}
        onClose={() => setShowDrillGcodeModal(false)}
        boardId={topstack?.id}
        drillFiles={drillFiles}
        topSvg={topstack?.svg}
      />

      <AnimatePresence>
        {showDeleteConfirm && (
          <motion.div
            className="fixed inset-0 bg-black/30 backdrop-blur-[2px] flex items-center justify-center z-50 dark:bg-slate-950/70"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ scale: 0.94, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.94, opacity: 0 }}
              transition={{ type: "spring", stiffness: 260, damping: 20 }}
              className="bg-white rounded-xl p-5 w-[300px] space-y-4 shadow-xl dark:bg-slate-900 dark:border dark:border-slate-800"
            >
              <div className="space-y-1">
                <p className="text-sm font-semibold text-gray-800 dark:text-slate-100">
                  Delete all outputs?
                </p>
                <p className="text-xs text-gray-500 dark:text-slate-400">
                  This will permanently remove{" "}
                  <span className="font-medium text-gray-700 dark:text-slate-200">
                    {pngFiles.length} PNG file
                    {pngFiles.length !== 1 && "s"}
                  </span>{" "}
                  from this session.
                </p>
              </div>

              <div className="text-[11px] text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/25">
                This action cannot be undone.
              </div>

              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-3 py-1.5 text-xs rounded-xl bg-slate-100 hover:bg-slate-200 transition dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAll}
                  className="px-3 py-1.5 text-xs rounded-xl bg-red-500 text-white hover:bg-red-600 transition dark:bg-red-500 dark:hover:bg-red-400"
                >
                  Delete All
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* PANELS */}
      <BulkLayoutPanel
        showBulkModal={showBulkModal}
        setShowBulkModal={setShowBulkModal}
      />

      {tabEditorPng && (
        <OutlineTabsModal
          png={tabEditorPng}
          outlineToolWidth={outlineToolWidth}
          preset={outlineTabPreset}
          onClose={() => setTabEditorPng(null)}
          onApply={handleApplyTabs}
          onRemove={handleRemoveTabs}
          onSavePreset={handleSaveTabPreset}
        />
      )}

      {previewPng && (
        <PngPreviewModal
          png={previewPng}
          onClose={() => setPreviewPng(null)}
        />
      )}

      <AnimatePresence>
        {lightBurnPng && (
          <LightBurnExportModal
            png={lightBurnPng}
            onClose={() => setLightBurnPng(null)}
          />
        )}
      </AnimatePresence>

      <ModsPanel
        showModsPanel={showModsPanel}
        setShowModsPanel={setShowModsPanel}
        selectedPng={selectedPng}
        setSelectedPng={setSelectedPng}
      />
    </>
  );
};

export default OutputPanel;

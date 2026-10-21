import React, { useRef, useState, useEffect } from 'react';
import {
  UploadCloud,
  FolderUp,
  Folder,
  X,
  Sliders,
  Layers,
  Scan,
  RefreshCw,
  AlertTriangle,
  FileText,
  Trash2,
  CheckCircle2,
  Image as ImageIcon,
  ChevronRight,
  Eye
} from 'lucide-react';
import { DEFAULT_CONF, DEFAULT_CLASSIFY_CROPS } from '../config';

export default function Uploader({
  selectedFiles,
  detectedFolder,
  primaryPreview,
  activePreviewIndex,
  setActivePreviewIndex,
  confThreshold,
  setConfThreshold,
  classifyCrops,
  setClassifyCrops,
  isProcessing,
  activeStepText,
  scanningProgress,
  errorMsg,
  onFilesSelected,
  onRemoveFile,
  onClearAll,
  onRunInspection,
  onLoadPreset,
}) {
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  // Cached object URLs for visual thumbnail preview strip
  const [filePreviews, setFilePreviews] = useState([]);

  useEffect(() => {
    // Generate object URLs for the first 30 files for responsive visual thumbnails
    const urls = selectedFiles.slice(0, 30).map((file) => ({
      file,
      url: URL.createObjectURL(file),
      name: file.name,
      size: (file.size / 1024).toFixed(1) + ' KB',
    }));
    setFilePreviews(urls);

    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u.url));
    };
  }, [selectedFiles]);

  // Filter helper: keep only jpg, jpeg, png, bmp
  const filterSupportedImages = (files) => {
    return Array.from(files).filter((file) =>
      /\.(jpe?g|png|bmp)$/i.test(file.name)
    );
  };

  // Recursive directory reader for drag & drop of folders
  const readEntryRecursively = async (entry) => {
    if (entry.isFile) {
      return new Promise((resolve) => {
        entry.file(
          (file) => resolve([file]),
          () => resolve([])
        );
      });
    } else if (entry.isDirectory) {
      const dirReader = entry.createReader();
      const entries = await new Promise((resolve) => {
        const allEntries = [];
        const readBatch = () => {
          dirReader.readEntries(
            (results) => {
              if (!results.length) {
                resolve(allEntries);
              } else {
                allEntries.push(...results);
                readBatch();
              }
            },
            () => resolve(allEntries)
          );
        };
        readBatch();
      });
      const nested = await Promise.all(entries.map(readEntryRecursively));
      return nested.flat();
    }
    return [];
  };

  // Handle Drag & Drop
  const handleDrop = async (e) => {
    e.preventDefault();
    let gatheredFiles = [];
    let folderDetected = '';

    const items = e.dataTransfer.items;
    if (items && items.length > 0) {
      const entryPromises = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const entry = item.webkitGetAsEntry
          ? item.webkitGetAsEntry()
          : item.getAsEntry
          ? item.getAsEntry()
          : null;

        if (entry) {
          if (entry.isDirectory && !folderDetected) {
            folderDetected = entry.name;
          }
          entryPromises.push(readEntryRecursively(entry));
        } else {
          const f = item.getAsFile();
          if (f) gatheredFiles.push(f);
        }
      }
      const resolved = await Promise.all(entryPromises);
      gatheredFiles = [...gatheredFiles, ...resolved.flat()];
    } else if (e.dataTransfer.files) {
      gatheredFiles = Array.from(e.dataTransfer.files);
    }

    const validImages = filterSupportedImages(gatheredFiles);
    onFilesSelected(validImages, folderDetected);
  };

  // Handle File Input Change
  const handleFilesChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const validImages = filterSupportedImages(e.target.files);
      onFilesSelected(validImages, '');
      e.target.value = '';
    }
  };

  // Handle Folder Input Change
  const handleFolderChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      let folderName = '';
      if (files[0] && files[0].webkitRelativePath) {
        folderName = files[0].webkitRelativePath.split('/')[0];
      }
      const validImages = filterSupportedImages(files);
      onFilesSelected(validImages, folderName);
      e.target.value = '';
    }
  };

  return (
    <div className="rounded-3xl p-6 sm:p-7 border bg-white border-[#e8dfd5] shadow-[0_4px_25px_-5px_rgba(217,119,6,0.06)] transition-all">
      {/* Station Title & Quick Presets */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-[#f0e7db]">
        <div>
          <h2 className="font-extrabold text-xl tracking-tight text-slate-900 flex items-center space-x-2">
            <span>PCB Image & Batch Uploader</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Select high-resolution PCB photos, multiple files, or an entire folder hierarchy.
          </p>
        </div>

        {/* Quick Test Presets */}
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-mono font-semibold uppercase text-slate-400">
            Presets:
          </span>
          <button
            type="button"
            onClick={() => onLoadPreset('demo1')}
            className="px-3 py-1.5 rounded-lg border text-xs font-semibold bg-[#faf6f0] border-[#dfd4c4] text-amber-900 hover:bg-amber-100/60 transition-all cursor-pointer shadow-xs"
          >
            Sample Board #01
          </button>
        </div>
      </div>

      {/* Main Drag & Drop Zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !primaryPreview && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-6 text-center transition-all ${
          primaryPreview
            ? 'border-amber-400/80 bg-amber-50/20'
            : 'border-[#d4c6b5] hover:border-amber-600/80 bg-[#fbf9f5] hover:bg-amber-50/40 cursor-pointer'
        }`}
      >
        {/* Hidden native inputs */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*"
          onChange={handleFilesChange}
          className="hidden"
          id="file-input-multiple"
        />
        <input
          ref={folderInputRef}
          type="file"
          webkitdirectory=""
          directory=""
          multiple
          onChange={handleFolderChange}
          className="hidden"
          id="folder-input"
        />

        {primaryPreview ? (
          /* Active Image Visual Preview */
          <div className="relative group overflow-hidden rounded-xl max-h-56 flex items-center justify-center bg-[#1a2e22]/5">
            <img
              src={primaryPreview}
              alt="Uploaded PCB preview"
              className="object-contain w-full h-full max-h-52 rounded-xl transition-transform group-hover:scale-102"
            />
            <div
              onClick={() => fileInputRef.current?.click()}
              className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-medium space-x-2 cursor-pointer backdrop-blur-2xs"
            >
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Click or drop new images to replace</span>
            </div>
          </div>
        ) : (
          /* Dropzone Placeholder */
          <div className="py-6 flex flex-col items-center">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-3 bg-amber-500/10 text-amber-800 border border-amber-500/20 shadow-xs">
              <UploadCloud className="w-7 h-7" />
            </div>
            <h4 className="font-bold text-base text-slate-900 mb-1">
              Drag & Drop PCB Photos or Entire Folder Here
            </h4>
            <p className="text-xs text-slate-500 max-w-sm mb-4">
              Supports JPG, JPEG, PNG, and BMP formats. Non-images will be filtered out automatically.
            </p>
          </div>
        )}

        {/* Buttons to Trigger Multi-Files or Folder */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            className="py-2 px-4 rounded-xl border border-[#d8ccbc] bg-white text-slate-800 hover:bg-amber-50 text-xs font-bold flex items-center space-x-2 shadow-xs cursor-pointer transition-all active:scale-95"
          >
            <UploadCloud className="w-4 h-4 text-amber-700" />
            <span>Select Images (Multiple)</span>
          </button>

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              folderInputRef.current?.click();
            }}
            className="py-2 px-4 rounded-xl border border-amber-400 bg-amber-50 text-amber-950 hover:bg-amber-100 text-xs font-bold flex items-center space-x-2 shadow-xs cursor-pointer transition-all active:scale-95"
          >
            <FolderUp className="w-4 h-4 text-amber-800" />
            <span>Select Folder</span>
          </button>
        </div>
      </div>

      {/* Found Images Notification Banner */}
      {selectedFiles.length > 0 && (
        <div className="mt-5 p-4 rounded-2xl border bg-amber-50/90 border-amber-300 text-amber-950 flex flex-wrap items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center space-x-3">
            <Folder className="w-5 h-5 text-amber-800 shrink-0" />
            <div>
              <span className="font-bold text-sm block">
                {detectedFolder
                  ? `Found ${selectedFiles.length} images in folder '${detectedFolder}'`
                  : `Found ${selectedFiles.length} images selected`}
              </span>
              <span className="text-[11px] text-slate-600 font-mono">
                {selectedFiles.length > 50
                  ? `Auto-chunking into ${Math.ceil(selectedFiles.length / 50)} batches (50 per batch limit)`
                  : 'Ready for batch GPU inference'}
              </span>
            </div>
          </div>

          <button
            onClick={onClearAll}
            className="py-1 px-3 rounded-lg border border-slate-300 bg-white hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-xs font-semibold flex items-center space-x-1.5 cursor-pointer transition-all"
            title="Clear selection"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear All</span>
          </button>
        </div>
      )}

      {/* Visual Uploaded Thumbnails Strip (shows what was uploaded!) */}
      {filePreviews.length > 0 && (
        <div className="mt-4 p-4 rounded-2xl border border-[#e8dfd5] bg-[#fbf9f5]">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-2.5">
            <span>Uploaded Images Preview ({selectedFiles.length}):</span>
            <span className="font-mono text-[11px] text-slate-400">
              Showing {filePreviews.length} of {selectedFiles.length} • Click to inspect
            </span>
          </div>

          {/* Horizontal scrollable visual cards strip */}
          <div className="flex space-x-3 overflow-x-auto pb-2 pt-1 pr-1">
            {filePreviews.map((item, idx) => (
              <div
                key={`${item.name}_${idx}`}
                onClick={() => setActivePreviewIndex && setActivePreviewIndex(idx)}
                className={`relative shrink-0 w-28 rounded-xl border p-1.5 transition-all cursor-pointer group bg-white shadow-xs ${
                  activePreviewIndex === idx
                    ? 'border-amber-600 ring-2 ring-amber-500/20'
                    : 'border-[#e0d4c5] hover:border-amber-400'
                }`}
              >
                {/* Thumbnail Image */}
                <div className="w-full h-16 rounded-lg overflow-hidden bg-slate-900/5 flex items-center justify-center">
                  <img
                    src={item.url}
                    alt={item.name}
                    className="w-full h-full object-contain"
                  />
                </div>

                {/* Info & Remove */}
                <div className="mt-1.5 px-0.5">
                  <p className="text-[10px] font-mono font-medium text-slate-800 truncate" title={item.name}>
                    {item.name}
                  </p>
                  <p className="text-[9px] font-mono text-slate-400">{item.size}</p>
                </div>

                {/* Remove button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveFile(idx);
                  }}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-xs hover:bg-red-700 cursor-pointer"
                  title="Remove this image"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hyperparameters Controls Row */}
      <div className="mt-6 pt-5 border-t border-[#f0e7db] grid grid-cols-1 md:grid-cols-2 gap-5 items-center">
        {/* Confidence Threshold Slider: 0.05 to 0.90, default 0.25 */}
        <div>
          <div className="flex justify-between items-center text-xs font-semibold mb-2">
            <span className="flex items-center space-x-1.5 text-slate-700">
              <span>Confidence Threshold</span>
              <span className="text-slate-400 text-[10px] font-normal">(0.05 - 0.90)</span>
            </span>
            <span className="font-mono font-bold text-xs px-2 py-0.5 rounded border bg-amber-500/10 border-amber-500/25 text-amber-800">
              {confThreshold.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min="0.05"
            max="0.90"
            step="0.01"
            value={confThreshold}
            onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
            className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-amber-700 bg-slate-200"
          />
          <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
            <span>0.05 (Sensitive)</span>
            <span>Default: 0.25</span>
            <span>0.90 (Strict)</span>
          </div>
        </div>

        {/* Secondary Crop Classifier Checkbox */}
        <div className="flex items-center justify-between p-3.5 rounded-xl border border-[#e0d4c5] bg-[#faf6f0]">
          <div>
            <label
              htmlFor="classify-crops-toggle"
              className="text-xs font-bold text-slate-800 cursor-pointer block"
            >
              EfficientNet-B0 Verification
            </label>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Refines detected crop bounding boxes
            </p>
          </div>
          <input
            id="classify-crops-toggle"
            type="checkbox"
            checked={classifyCrops}
            onChange={(e) => setClassifyCrops(e.target.checked)}
            className="w-5 h-5 rounded border-slate-300 text-amber-700 accent-amber-700 focus:ring-amber-500 cursor-pointer"
          />
        </div>
      </div>

      {/* Error Message Notice Banner */}
      {errorMsg && (
        <div className="mt-5 p-3.5 rounded-xl border border-red-300 bg-red-50 text-red-800 text-xs flex items-center space-x-2.5 animate-in fade-in duration-200">
          <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Progress Bar (aria-live="polite") */}
      {isProcessing && (
        <div
          role="status"
          aria-live="polite"
          className="mt-6 p-4 rounded-2xl border border-amber-300 bg-amber-50/70"
        >
          <div className="flex items-center justify-between text-xs font-mono font-semibold text-amber-900 mb-2">
            <span className="flex items-center space-x-2">
              <RefreshCw className="w-4 h-4 animate-spin text-amber-700" />
              <span>{activeStepText || 'Processing inference pipeline...'}</span>
            </span>
            <span>{scanningProgress}%</span>
          </div>

          <div className="w-full h-2.5 rounded-full overflow-hidden bg-amber-200/60 border border-amber-300">
            <div
              className="h-full bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 rounded-full transition-all duration-300"
              style={{ width: `${scanningProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Run Inspection CTA Action */}
      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={onRunInspection}
          disabled={isProcessing || selectedFiles.length === 0}
          className="w-full sm:w-auto px-8 py-3.5 rounded-xl text-xs font-bold text-white uppercase tracking-wider flex items-center justify-center space-x-2 transition-all shadow-md cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 hover:from-amber-700 hover:to-amber-900 shadow-amber-700/20 hover:shadow-lg active:scale-95"
        >
          <Scan className="w-4 h-4" />
          <span>
            {isProcessing
              ? 'Analyzing Layers...'
              : `Run Inspection (${selectedFiles.length} Image${selectedFiles.length === 1 ? '' : 's'})`}
          </span>
        </button>
      </div>
    </div>
  );
}

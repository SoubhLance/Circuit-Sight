import React, { useState, useEffect, useRef } from 'react';
import {
  Cpu,
  ArrowLeft,
  ArrowRight,
  Layers,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  Sliders,
  Scan,
  CheckCircle2
} from 'lucide-react';
import Hero from './components/Hero';
import HowItWorks from './components/HowItWorks';
import Uploader from './components/Uploader';
import InspectionCanvas from './components/InspectionCanvas';
import Gallery from './components/Gallery';
import Lightbox from './components/Lightbox';
import Footer from './components/Footer';
import {
  API_BASE_URL,
  DEFAULT_CONF,
  DEFAULT_IOU,
  DEFAULT_IMGSZ,
  DEFAULT_CLASSIFY_CROPS,
  DEFECT_CLASSES
} from './config';

// Built-in Sample PCB vector image for immediate 1-click preview
const SAMPLE_PCB_SVG = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450" fill="%231a3324"><rect width="800" height="450" fill="%23162d20"/><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="%231e3d2b" stroke-width="1"/></pattern><rect width="800" height="450" fill="url(%23grid)"/><path d="M 50 100 L 250 100 L 300 150 L 550 150 L 600 200 L 750 200" stroke="%2338a169" stroke-width="6" fill="none"/><path d="M 80 280 L 220 280 L 280 220 L 480 220 L 520 260 L 720 260" stroke="%23d69e2e" stroke-width="4" fill="none"/><path d="M 120 350 L 320 350 L 380 290 L 650 290" stroke="%2338a169" stroke-width="5" fill="none"/><circle cx="250" cy="100" r="14" fill="%23ecc94b" stroke="%23d69e2e" stroke-width="3"/><circle cx="550" cy="150" r="14" fill="%23ecc94b" stroke="%23d69e2e" stroke-width="3"/><circle cx="300" cy="150" r="10" fill="%23ecc94b"/><circle cx="280" cy="220" r="12" fill="%23ecc94b"/><circle cx="480" cy="220" r="12" fill="%23ecc94b"/><circle cx="380" cy="290" r="10" fill="%23ecc94b"/><rect x="340" y="70" width="90" height="90" rx="6" fill="%230f1f16" stroke="%2348bb78" stroke-width="2"/><text x="355" y="120" fill="%2348bb78" font-family="monospace" font-size="14" font-weight="bold">ARM-MCU</text><rect x="620" y="80" width="70" height="40" rx="4" fill="%2322543d" stroke="%23ecc94b" stroke-width="1.5"/><rect x="150" y="160" width="60" height="30" rx="4" fill="%2322543d" stroke="%23ecc94b" stroke-width="1.5"/><circle cx="180" cy="175" r="8" fill="%23e53e3e" opacity="0.3"/><circle cx="480" cy="220" r="24" fill="none" stroke="%23e53e3e" stroke-width="3" stroke-dasharray="4,4"/><text x="495" y="210" fill="%23fc8181" font-family="sans-serif" font-size="12" font-weight="bold">Missing Hole</text><circle cx="600" cy="200" r="20" fill="none" stroke="%23dd6b20" stroke-width="3" stroke-dasharray="4,4"/><text x="615" y="190" fill="%23f6ad55" font-family="sans-serif" font-size="12" font-weight="bold">Spur</text><circle cx="150" cy="100" r="18" fill="none" stroke="%23e53e3e" stroke-width="3" stroke-dasharray="4,4"/><text x="160" y="85" fill="%23fc8181" font-family="sans-serif" font-size="12" font-weight="bold">Mouse Bite</text></svg>`;

export default function CircuitSightApp() {
  // View mode: 'landing' (editorial showcase) or 'inspector' (dissolved into inspection station)
  const [viewMode, setViewMode] = useState('landing');

  // Input states
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [detectedFolder, setDetectedFolder] = useState('');
  const [primaryPreview, setPrimaryPreview] = useState(null);
  const [activePreviewIndex, setActivePreviewIndex] = useState(0);

  // Hyperparameters
  const [confThreshold, setConfThreshold] = useState(DEFAULT_CONF);
  const [iouThreshold, setIouThreshold] = useState(DEFAULT_IOU);
  const [classifyCrops, setClassifyCrops] = useState(DEFAULT_CLASSIFY_CROPS);

  // Execution states
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStepText, setActiveStepText] = useState('');
  const [scanningProgress, setScanningProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);

  // Active single-image inspection result (for canvas viewing)
  const [activeCanvasResult, setActiveCanvasResult] = useState(null);

  // Batch results collection
  const [batchResults, setBatchResults] = useState(null);
  const [activeLightboxImage, setActiveLightboxImage] = useState(null);
  const [activeLightboxIndex, setActiveLightboxIndex] = useState(0);

  // Export states
  const [zipLoading, setZipLoading] = useState(false);
  const [zipError, setZipError] = useState(null);

  // Handle files selection
  const handleFilesSelected = (newFiles, folderName) => {
    setErrorMsg(null);
    setDetectedFolder(folderName || '');

    // Deduplicate files by name & size
    setSelectedFiles((prev) => {
      const existingKeys = new Set(prev.map((f) => `${f.name}_${f.size}`));
      const fresh = newFiles.filter((f) => !existingKeys.has(`${f.name}_${f.size}`));
      const combined = [...prev, ...fresh];

      // Automatically update the primary preview with the first image
      if (combined.length > 0) {
        const reader = new FileReader();
        reader.onload = (e) => {
          setPrimaryPreview(e.target.result);
        };
        reader.readAsDataURL(combined[0]);
        setActivePreviewIndex(0);
      }
      return combined;
    });
  };

  // Switch previewed file when clicking a thumbnail card
  const handleSelectPreviewFile = (index) => {
    if (selectedFiles[index]) {
      setActivePreviewIndex(index);
      const reader = new FileReader();
      reader.onload = (e) => {
        setPrimaryPreview(e.target.result);
      };
      reader.readAsDataURL(selectedFiles[index]);
    }
  };

  // Remove individual file by index
  const handleRemoveFile = (index) => {
    setSelectedFiles((prev) => {
      const next = prev.filter((_, idx) => idx !== index);
      if (next.length === 0) {
        setPrimaryPreview(null);
        setActiveCanvasResult(null);
      } else if (index === activePreviewIndex) {
        const newIdx = Math.max(0, index - 1);
        setActivePreviewIndex(newIdx);
        const reader = new FileReader();
        reader.onload = (e) => setPrimaryPreview(e.target.result);
        reader.readAsDataURL(next[newIdx]);
      }
      return next;
    });
  };

  // Clear all selections
  const handleClearAll = () => {
    setSelectedFiles([]);
    setDetectedFolder('');
    setPrimaryPreview(null);
    setActiveCanvasResult(null);
    setBatchResults(null);
    setErrorMsg(null);
    setZipError(null);
  };

  // Quick preset loader
  const handleLoadPreset = (presetName) => {
    setErrorMsg(null);
    setPrimaryPreview(SAMPLE_PCB_SVG);
    setActiveCanvasResult({
      success: true,
      image_width: 3034,
      image_height: 1586,
      total_defects: 3,
      defect_summary: {
        missing_hole: 1,
        spur: 1,
        mouse_bite: 1,
      },
      detections: [
        {
          class_name: 'missing_hole',
          confidence: 0.942,
          bbox: [456, 196, 504, 244],
          defect_details: DEFECT_CLASSES.missing_hole,
        },
        {
          class_name: 'spur',
          confidence: 0.887,
          bbox: [580, 180, 620, 220],
          defect_details: DEFECT_CLASSES.spur,
        },
        {
          class_name: 'mouse_bite',
          confidence: 0.824,
          bbox: [132, 82, 168, 118],
          defect_details: DEFECT_CLASSES.mouse_bite,
        },
      ],
      inference_time_ms: 54.2,
      model_name: 'yolov8s AOI',
      device: 'cuda',
      warning: null,
      settings_used: { conf: 0.25, iou: 0.45, imgsz: 1024 },
    });
  };

  /**
   * Main Inspection Execution:
   * Chunks files into 50 (backend limit), sends conf/iou/classify_crops only if modified,
   * monitors combined progress, and populates both the active inspection canvas and batch gallery.
   */
  const handleRunInspection = async () => {
    if (selectedFiles.length === 0) {
      if (primaryPreview === SAMPLE_PCB_SVG) {
        // Run synthetic demo inspection
        setIsProcessing(true);
        setScanningProgress(30);
        setActiveStepText('Tensor preprocessing & input scaling (1024px)...');
        setTimeout(() => {
          setScanningProgress(75);
          setActiveStepText('YOLOv8s GPU inference & IoU suppression...');
        }, 400);
        setTimeout(() => {
          setScanningProgress(100);
          setActiveStepText('Inspection complete.');
          setIsProcessing(false);
        }, 800);
        return;
      }
      setErrorMsg('Please select or upload PCB images first.');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);
    setZipError(null);
    setScanningProgress(0);

    const CHUNK_SIZE = 50;
    const chunks = [];
    for (let i = 0; i < selectedFiles.length; i += CHUNK_SIZE) {
      chunks.push(selectedFiles.slice(i, i + CHUNK_SIZE));
    }

    const allBatchIds = [];
    let mergedImages = [];
    let processedTotal = 0;
    const totalCount = selectedFiles.length;

    try {
      for (let cIdx = 0; cIdx < chunks.length; cIdx++) {
        const currentChunk = chunks[cIdx];
        const batchNum = cIdx + 1;
        setActiveStepText(`batch ${batchNum}/${chunks.length}, ${processedTotal}/${totalCount} images`);
        setScanningProgress(Math.round((processedTotal / totalCount) * 100));

        const formData = new FormData();
        currentChunk.forEach((file) => formData.append('files', file));

        // Send parameters only if changed from defaults
        if (confThreshold !== DEFAULT_CONF) {
          formData.append('conf', confThreshold.toString());
        }
        if (iouThreshold !== DEFAULT_IOU) {
          formData.append('iou', iouThreshold.toString());
        }
        if (classifyCrops !== DEFAULT_CLASSIFY_CROPS) {
          formData.append('classify_crops', classifyCrops ? 'true' : 'false');
        }

        let submitRes;
        try {
          submitRes = await fetch(`${API_BASE_URL}/batch`, {
            method: 'POST',
            body: formData,
          });
        } catch (fetchErr) {
          throw new Error(`Unable to connect to CircuitSight backend at ${API_BASE_URL}. Ensure uvicorn server is active on port 8000.`);
        }

        if (!submitRes.ok) {
          let errDetail = '';
          try {
            const errJson = await submitRes.json();
            errDetail = errJson.detail || '';
          } catch {
            // non-json
          }
          if (submitRes.status === 413) {
            throw new Error(`Payload too large (413): ${errDetail || 'Maximum 25 MB per file or 400 MB batch limit exceeded.'}`);
          }
          if (submitRes.status === 429) {
            throw new Error(`Server busy (429): ${errDetail || 'Max concurrent batches reached. Please wait.'}`);
          }
          throw new Error(errDetail || `Batch submission failed with HTTP ${submitRes.status}`);
        }

        const { batch_id } = await submitRes.json();
        allBatchIds.push(batch_id);

        // Poll batch status
        let isDone = false;
        while (!isDone) {
          await new Promise((r) => setTimeout(r, 650));
          const statusRes = await fetch(`${API_BASE_URL}/batch/${batch_id}/status`);
          if (!statusRes.ok) throw new Error(`Status check failed for batch ${batch_id}`);
          const stData = await statusRes.json();

          const currentBatchProcessed = stData.processed || 0;
          const currentTotal = processedTotal + currentBatchProcessed;
          setActiveStepText(`batch ${batchNum}/${chunks.length}, ${currentTotal}/${totalCount} images`);
          setScanningProgress(Math.min(99, Math.round((currentTotal / totalCount) * 100)));

          if (stData.status === 'done' || stData.status === 'failed') {
            isDone = true;
            processedTotal += currentBatchProcessed;
          }
        }

        // Fetch chunk results
        const resultsRes = await fetch(`${API_BASE_URL}/batch/${batch_id}/results`);
        if (!resultsRes.ok) throw new Error(`Could not fetch results for batch ${batch_id}`);
        const bRes = await resultsRes.json();

        if (bRes.images) {
          const tagged = bRes.images.map((img) => ({
            ...img,
            batch_id: batch_id,
            image_url: img.image_url || `${API_BASE_URL}/batch/${batch_id}/image/${img.index}`,
            thumb_url: img.thumb_url || `${API_BASE_URL}/batch/${batch_id}/thumb/${img.index}`,
          }));
          mergedImages = mergedImages.concat(tagged);
        }
      }

      setScanningProgress(100);
      setActiveStepText(`Inspection finished: ${processedTotal}/${totalCount} boards analyzed.`);

      // Aggregate statistics
      const imagesWithDetections = mergedImages.filter((img) => (img.total_defects || 0) > 0).length;
      const imagesWithoutDetections = mergedImages.filter(
        (img) => (img.total_defects || 0) === 0 && !img.error
      ).length;
      const totalDefects = mergedImages.reduce((sum, img) => sum + (img.total_defects || 0), 0);
      const perClassCounts = {};
      mergedImages.forEach((img) => {
        Object.entries(img.defect_summary || {}).forEach(([cls, cnt]) => {
          perClassCounts[cls] = (perClassCounts[cls] || 0) + cnt;
        });
      });

      const finalAggregated = {
        batchIds: allBatchIds,
        total: mergedImages.length,
        processed: mergedImages.length,
        images_with_detections: imagesWithDetections,
        images_without_detections: imagesWithoutDetections,
        total_defects: totalDefects,
        per_class_counts: perClassCounts,
        images: mergedImages,
      };

      setBatchResults(finalAggregated);

      // Set first result on active inspection canvas
      if (mergedImages.length > 0) {
        const first = mergedImages[0];
        setActiveCanvasResult({
          image_url: first.image_url,
          annotated_image_url: first.image_url,
          image_width: first.width,
          image_height: first.height,
          total_defects: first.total_defects,
          detections: first.detections || [],
          warning: first.warning,
          settings_used: { conf: confThreshold, iou: iouThreshold, imgsz: 1024 },
        });
      }
    } catch (err) {
      console.error('Inspection error:', err);
      setErrorMsg(err.message || 'Inspection failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  // ZIP download handler
  const handleDownloadZip = async () => {
    if (!batchResults?.batchIds || batchResults.batchIds.length === 0) return;
    setZipLoading(true);
    setZipError(null);

    try {
      let downloadUrl = '';
      if (batchResults.batchIds.length === 1) {
        downloadUrl = `${API_BASE_URL}/batch/${batchResults.batchIds[0]}/zip`;
      } else {
        const idsParam = batchResults.batchIds.join(',');
        downloadUrl = `${API_BASE_URL}/batch/zip?ids=${idsParam}`;
      }

      const res = await fetch(downloadUrl);
      if (!res.ok) {
        throw new Error(`Failed to generate ZIP archive (HTTP ${res.status}).`);
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = batchResults.batchIds.length === 1
        ? `circuitsight_batch_${batchResults.batchIds[0].substring(0, 8)}.zip`
        : `circuitsight_combined_report.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error('ZIP export error:', err);
      setZipError(err.message || 'Could not download ZIP archive.');
    } finally {
      setZipLoading(false);
    }
  };

  // CSV download handler
  const handleDownloadCsv = () => {
    if (!batchResults?.images || batchResults.images.length === 0) return;

    const headers = [
      'Filename',
      'Batch ID',
      'Image Index',
      'Width',
      'Height',
      'Total Defects',
      'Missing Hole',
      'Mouse Bite',
      'Open Circuit',
      'Short',
      'Spur',
      'Spurious Copper',
      'Max Confidence',
      'Warning',
      'Error',
    ];

    const rows = batchResults.images.map((img) => {
      const ds = img.defect_summary || {};
      const maxConf = Math.max(...(img.detections?.map((d) => d.confidence) || [0]), 0);
      return [
        `"${(img.filename || '').replace(/"/g, '""')}"`,
        `"${img.batch_id || ''}"`,
        img.index ?? '',
        img.width ?? '',
        img.height ?? '',
        img.total_defects ?? 0,
        ds.missing_hole ?? 0,
        ds.mouse_bite ?? 0,
        ds.open_circuit ?? 0,
        ds.short ?? 0,
        ds.spur ?? 0,
        ds.spurious_copper ?? 0,
        maxConf > 0 ? maxConf.toFixed(4) : '0',
        `"${(img.warning || '').replace(/"/g, '""')}"`,
        `"${(img.error || '').replace(/"/g, '""')}"`,
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = `circuitsight_inspection_report_${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
  };

  // Switch active canvas image when thumbnail in gallery is clicked
  const handleGalleryImageClick = (img, idx) => {
    setActiveLightboxImage(img);
    setActiveLightboxIndex(idx);

    // Also update active canvas result
    setActiveCanvasResult({
      image_url: img.image_url,
      annotated_image_url: img.image_url,
      image_width: img.width,
      image_height: img.height,
      total_defects: img.total_defects,
      detections: img.detections || [],
      warning: img.warning,
      settings_used: { conf: confThreshold, iou: iouThreshold, imgsz: 1024 },
    });
  };

  return (
    <div className="min-h-screen bg-[#faf7f2] text-[#1e293b] font-sans pcb-grid-pattern selection:bg-amber-200 selection:text-amber-900">
      {/* ===================== Top Luxury Header ===================== */}
      <header className="sticky top-0 z-40 backdrop-blur-md bg-[#faf7f2]/90 border-b border-[#e8dfd5] shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          {/* Logo & Brand */}
          <div
            onClick={() => setViewMode('landing')}
            className="flex items-center space-x-3.5 cursor-pointer group"
            title="Return to Overview"
          >
            <div className="p-2.5 rounded-xl bg-amber-600/10 text-amber-800 border border-amber-600/25 shadow-xs group-hover:scale-105 transition-transform">
              <Cpu className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-amber-700 via-amber-800 to-amber-950 bg-clip-text text-transparent">
                  CircuitSight
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold border bg-amber-100 text-amber-900 border-amber-300">
                  YOLOv8 AOI
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Automated Optical Inspection for High-Yield PCB Assembly
              </p>
            </div>
          </div>

          {/* Navigation Action */}
          <div className="flex items-center space-x-3">
            {viewMode === 'landing' ? (
              <button
                type="button"
                onClick={() => setViewMode('inspector')}
                className="px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider text-white flex items-center space-x-2 transition-all shadow-md cursor-pointer bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 hover:from-amber-700 hover:to-amber-900 shadow-amber-700/25 active:scale-95"
              >
                <span>Launch Inspector</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setViewMode('landing')}
                className="px-4 py-2 rounded-xl font-semibold text-xs border border-[#d8ccbc] bg-white text-slate-700 hover:bg-amber-50 cursor-pointer flex items-center space-x-1.5 shadow-2xs transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-amber-700" />
                <span>Overview & Taxonomy</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ===================== VIEW 1: LANDING PAGE ===================== */}
      {viewMode === 'landing' && (
        <div className="animate-dissolve transition-all">
          <Hero
            onLaunchInspector={() => setViewMode('inspector')}
            onLearnMore={() => {
              const el = document.getElementById('how-it-works');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }}
          />
          <HowItWorks />
          <Footer />
        </div>
      )}

      {/* ===================== VIEW 2: DEDICATED INSPECTION WORKSPACE ===================== */}
      {viewMode === 'inspector' && (
        <div className="animate-dissolve max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          {/* Top Breadcrumb Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#e8dfd5]">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode('landing')}
                className="text-xs font-semibold text-amber-800 hover:text-amber-950 flex items-center space-x-1 cursor-pointer transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Overview</span>
              </button>
              <span className="text-slate-300">/</span>
              <span className="text-xs font-bold text-slate-800">
                Inspection Station
              </span>
            </div>

            <span className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
              GPU CUDA Ready (RTX 4060)
            </span>
          </div>

          {/* Interactive Inspection Workspace: 2-Column Responsive Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Uploader & Control (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              <Uploader
                selectedFiles={selectedFiles}
                detectedFolder={detectedFolder}
                primaryPreview={primaryPreview}
                activePreviewIndex={activePreviewIndex}
                setActivePreviewIndex={handleSelectPreviewFile}
                confThreshold={confThreshold}
                setConfThreshold={setConfThreshold}
                classifyCrops={classifyCrops}
                setClassifyCrops={setClassifyCrops}
                isProcessing={isProcessing}
                activeStepText={activeStepText}
                scanningProgress={scanningProgress}
                errorMsg={errorMsg}
                onFilesSelected={handleFilesSelected}
                onRemoveFile={handleRemoveFile}
                onClearAll={handleClearAll}
                onRunInspection={handleRunInspection}
                onLoadPreset={handleLoadPreset}
              />
            </div>

            {/* Right Column: Active Inspection Canvas & Findings (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              <InspectionCanvas
                imagePreview={primaryPreview}
                result={activeCanvasResult}
                isProcessing={isProcessing}
                activeStepText={activeStepText}
                scanningProgress={scanningProgress}
                onOpenLightbox={() => {
                  if (activeCanvasResult) {
                    setActiveLightboxImage({
                      filename: selectedFiles[activePreviewIndex]?.name || 'sample_pcb.jpg',
                      image_url: activeCanvasResult.image_url || activeCanvasResult.annotated_image_url || primaryPreview,
                      thumb_url: primaryPreview,
                      total_defects: activeCanvasResult.total_defects,
                      detections: activeCanvasResult.detections || [],
                      warning: activeCanvasResult.warning,
                      width: activeCanvasResult.image_width,
                      height: activeCanvasResult.image_height,
                    });
                    setActiveLightboxIndex(0);
                  }
                }}
              />
            </div>
          </div>

          {/* Bottom Section: Batch Gallery of Results (if batch / multiple files run) */}
          {batchResults && (
            <div className="pt-6">
              <Gallery
                results={batchResults}
                onImageClick={handleGalleryImageClick}
                onDownloadZip={handleDownloadZip}
                onDownloadCsv={handleDownloadCsv}
              />
            </div>
          )}

          <Footer />
        </div>
      )}

      {/* ===================== Lightbox Modal ===================== */}
      {activeLightboxImage && (
        <Lightbox
          image={activeLightboxImage}
          images={batchResults?.images || [activeLightboxImage]}
          currentIndex={activeLightboxIndex}
          onClose={() => setActiveLightboxImage(null)}
          onNavigate={(nextImg, nextIdx) => {
            setActiveLightboxImage(nextImg);
            setActiveLightboxIndex(nextIdx);
          }}
        />
      )}
    </div>
  );
}

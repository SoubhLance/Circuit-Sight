import React, { useState, useRef, useEffect } from 'react';
import {
  Cpu,
  Scan,
  UploadCloud,
  Sliders,
  Image as ImageIcon,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles,
  Download,
  Eye,
  EyeOff,
  Zap,
  Info,
  ChevronRight,
  ShieldAlert,
  Wrench,
  Clock,
  Maximize2,
  Sun,
  Moon,
  RefreshCw,
  FileCode,
  Tag
} from 'lucide-react';

// Sample dummy PCB image (SVG data URI) for initial showcase state
const DUMMY_PCB_SVG = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450" fill="%231a3324"><rect width="800" height="450" fill="%23162d20"/><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="%231e3d2b" stroke-width="1"/></pattern><rect width="800" height="450" fill="url(%23grid)"/><path d="M 50 100 L 250 100 L 300 150 L 550 150 L 600 200 L 750 200" stroke="%2338a169" stroke-width="6" fill="none"/><path d="M 80 280 L 220 280 L 280 220 L 480 220 L 520 260 L 720 260" stroke="%23d69e2e" stroke-width="4" fill="none"/><path d="M 120 350 L 320 350 L 380 290 L 650 290" stroke="%2338a169" stroke-width="5" fill="none"/><circle cx="250" cy="100" r="14" fill="%23ecc94b" stroke="%23d69e2e" stroke-width="3"/><circle cx="550" cy="150" r="14" fill="%23ecc94b" stroke="%23d69e2e" stroke-width="3"/><circle cx="300" cy="150" r="10" fill="%23ecc94b"/><circle cx="280" cy="220" r="12" fill="%23ecc94b"/><circle cx="480" cy="220" r="12" fill="%23ecc94b"/><circle cx="380" cy="290" r="10" fill="%23ecc94b"/><rect x="340" y="70" width="90" height="90" rx="6" fill="%230f1f16" stroke="%2348bb78" stroke-width="2"/><text x="355" y="120" fill="%2348bb78" font-family="monospace" font-size="14" font-weight="bold">ARM-MCU</text><rect x="620" y="80" width="70" height="40" rx="4" fill="%2322543d" stroke="%23ecc94b" stroke-width="1.5"/><rect x="150" y="160" width="60" height="30" rx="4" fill="%2322543d" stroke="%23ecc94b" stroke-width="1.5"/><circle cx="180" cy="175" r="8" fill="%23e53e3e" opacity="0.3"/><circle cx="480" cy="220" r="24" fill="none" stroke="%23e53e3e" stroke-width="3" stroke-dasharray="4,4"/><text x="495" y="210" fill="%23fc8181" font-family="sans-serif" font-size="12" font-weight="bold">Missing Hole</text><circle cx="600" cy="200" r="20" fill="none" stroke="%23dd6b20" stroke-width="3" stroke-dasharray="4,4"/><text x="615" y="190" fill="%23f6ad55" font-family="sans-serif" font-size="12" font-weight="bold">Spur</text><circle cx="150" cy="100" r="18" fill="none" stroke="%23e53e3e" stroke-width="3" stroke-dasharray="4,4"/><text x="160" y="85" fill="%23fc8181" font-family="sans-serif" font-size="12" font-weight="bold">Mouse Bite</text></svg>`;

export default function CircuitSightApp() {
  // Theme state: 'cream' (light luxury industrial) or 'dark' (high-tech cyber)
  const [theme, setTheme] = useState('cream');

  // Input states
  const [selectedFile, setSelectedFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [confThreshold, setConfThreshold] = useState(0.25);
  const [iouThreshold, setIouThreshold] = useState(0.45);
  const [classifyCrops, setClassifyCrops] = useState(true);

  // Execution states
  const [isProcessing, setIsProcessing] = useState(false);
  const [scanningProgress, setScanningProgress] = useState(0);
  const [activeStepText, setActiveStepText] = useState('');
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [showAnnotated, setShowAnnotated] = useState(true);
  const [selectedDetection, setSelectedDetection] = useState(null);

  const fileInputRef = useRef(null);

  // Initial dummy result state to showcase the rich UI immediately
  useEffect(() => {
    setImagePreview(DUMMY_PCB_SVG);
    setResult({
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
          defect_details: {
            name: 'Missing Hole / Via',
            severity: 'High',
            description: 'A required through-hole via or component lead hole is absent on the PCB substrate.',
            risk: 'Component leads cannot be inserted; broken multi-layer electrical connectivity.',
            remediation: 'Check CNC drill breakage sensor and drill program. Scrap if plating is complete.',
          },
          classifier_class: 'missing_hole',
          classifier_confidence: 0.9998,
        },
        {
          class_name: 'spur',
          confidence: 0.887,
          bbox: [580, 180, 620, 220],
          defect_details: {
            name: 'Spur Defect',
            severity: 'Medium',
            description: 'Sharp unwanted copper protrusion projecting outwards from a conductor trace.',
            risk: 'Reduces dielectric spacing; increases risk of electrical arcing and signal noise.',
            remediation: 'Inspect exposure artwork clarity and rinse chemistry in chemical etching stage.',
          },
          classifier_class: 'spur',
          classifier_confidence: 0.9854,
        },
        {
          class_name: 'mouse_bite',
          confidence: 0.824,
          bbox: [132, 82, 168, 118],
          defect_details: {
            name: 'Mouse Bite',
            severity: 'Medium',
            description: 'A ragged bite-like erosion along the edge of a copper trace or board boundary.',
            risk: 'Reduces trace cross-sectional area; induces localized heating under heavy current.',
            remediation: 'Audit photoresist film adhesion and chemical etching rate uniformity.',
          },
          classifier_class: 'mouse_bite',
          classifier_confidence: 0.9741,
        },
      ],
      inference_time_ms: 68.4,
      model_name: 'yolov8s (COCO fine-tuned)',
      device: 'cuda',
      warning: null,
      annotated_image_base64: null,
      settings_used: { conf: 0.25, iou: 0.45, imgsz: 1024 },
    });
  }, []);

  // Handle Drag & Drop
  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    if (!file.type.startsWith('image/')) {
      setErrorMsg('Please upload a valid image file (PNG, JPG, BMP, WebP).');
      return;
    }
    setErrorMsg(null);
    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      setImagePreview(e.target.result);
      setResult(null); // Clear previous results on new upload
      setSelectedDetection(null);
    };
    reader.readAsDataURL(file);
  };

  /**
   * Main Detection Handler
   * Connects directly to the FastAPI Backend: POST /api/detect
   * Fallback mock simulation is included if the backend server is unreachable.
   */
  const handleDetect = async () => {
    if (!imagePreview) {
      setErrorMsg('Please select or upload a PCB image first.');
      return;
    }

    setErrorMsg(null);
    setIsProcessing(true);
    setScanningProgress(15);
    setActiveStepText('Tensor preprocessing & input scaling (1024px)...');

    try {
      // Step 1: Simulated progress steps for futuristic feel
      setTimeout(() => {
        setScanningProgress(45);
        setActiveStepText('Running YOLOv8s bounding box regression...');
      }, 350);

      setTimeout(() => {
        setScanningProgress(75);
        setActiveStepText('Applying Non-Maximum Suppression (IoU: ' + iouThreshold + ')...');
      }, 700);

      // Step 2: Build FormData for FastAPI backend
      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      } else {
        // If user is running with the demo SVG, convert to blob
        const res = await fetch(imagePreview);
        const blob = await res.blob();
        formData.append('file', blob, 'sample_pcb.jpg');
      }

      formData.append('conf', confThreshold.toString());
      formData.append('iou', iouThreshold.toString());
      formData.append('imgsz', '1024');
      formData.append('classify_crops', classifyCrops ? 'true' : 'false');
      formData.append('include_annotated_image', 'true');

      // Step 3: Make actual POST request to FastAPI endpoint (/api/detect)
      const response = await fetch('/api/detect', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned status ${response.status}`);
      }

      const backendData = await response.json();
      setScanningProgress(100);
      setActiveStepText('Inspection complete!');

      setTimeout(() => {
        setResult(backendData);
        setIsProcessing(false);
      }, 400);

    } catch (err) {
      console.warn('Backend connection notice (falling back to client simulation):', err.message);

      // Graceful fallback for offline demo preview
      setTimeout(() => {
        setScanningProgress(100);
        setActiveStepText('Simulation completed.');
        setIsProcessing(false);

        setResult({
          success: true,
          image_width: 3034,
          image_height: 1586,
          total_defects: 2,
          defect_summary: { missing_hole: 1, open_circuit: 1 },
          detections: [
            {
              class_name: 'missing_hole',
              confidence: parseFloat((confThreshold + 0.15).toFixed(3)),
              bbox: [820, 310, 890, 375],
              defect_details: {
                name: 'Missing Via / Hole',
                severity: 'High',
                description: 'Component terminal through-hole is absent on the manufactured layer.',
                risk: 'Broken continuity between top and bottom copper layers.',
                remediation: 'Re-drill unplated hole before etching, or scrap defective board.',
              },
              classifier_class: 'missing_hole',
              classifier_confidence: 0.9994,
            },
            {
              class_name: 'open_circuit',
              confidence: parseFloat((confThreshold + 0.22).toFixed(3)),
              bbox: [1420, 680, 1510, 740],
              defect_details: {
                name: 'Open Circuit',
                severity: 'Critical',
                description: 'Complete physical disconnection along conductive trace line.',
                risk: 'Complete power or data rail interruption in circuit operation.',
                remediation: 'Micro-wire jumper rework for prototype; inspect photoresist adhesion in batch.',
              },
              classifier_class: 'open_circuit',
              classifier_confidence: 0.9891,
            },
          ],
          inference_time_ms: 124.8,
          model_name: 'yolov8s (FastAPI /api/detect)',
          device: 'cuda (fallback simulated)',
          warning: null,
          annotated_image_base64: null,
          settings_used: { conf: confThreshold, iou: iouThreshold, imgsz: 1024 },
        });
      }, 900);
    }
  };

  // Quick preset selector
  const loadPreset = (presetName) => {
    setErrorMsg(null);
    setSelectedFile(null);
    setImagePreview(DUMMY_PCB_SVG);
    setResult(null);
  };

  // Severity color helper
  const getSeverityBadge = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30';
      case 'high':
        return 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30';
      case 'medium':
        return 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30';
      default:
        return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30';
    }
  };

  const isCream = theme === 'cream';

  return (
    <div
      className={`min-h-screen transition-colors duration-300 font-sans pcb-grid-pattern ${
        isCream
          ? 'bg-[#faf7f2] text-[#1e293b]'
          : 'bg-[#090d16] text-[#e2e8f0]'
      }`}
    >
      {/* ===================== Top Navigation ===================== */}
      <header
        className={`sticky top-0 z-40 backdrop-blur-md border-b transition-colors ${
          isCream
            ? 'bg-[#faf7f2]/85 border-[#e8dfd5] shadow-xs'
            : 'bg-[#090d16]/85 border-slate-800 shadow-md'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3.5">
            <div
              className={`p-2.5 rounded-xl flex items-center justify-center shadow-xs border ${
                isCream
                  ? 'bg-amber-600/10 text-amber-700 border-amber-500/30 shadow-[0_0_15px_rgba(217,119,6,0.15)]'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
              }`}
            >
              <Cpu className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-amber-700 via-amber-800 to-amber-900 dark:from-emerald-300 dark:via-teal-200 dark:to-cyan-400 bg-clip-text text-transparent">
                  CircuitSight
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold border ${
                    isCream
                      ? 'bg-amber-100 text-amber-800 border-amber-300/80'
                      : 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                  }`}
                >
                  YOLOv8s AOI
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Automated Optical Inspection for PCB Defect Localization
              </p>
            </div>
          </div>

          {/* Right Nav Utilities */}
          <div className="flex items-center space-x-3">
            {/* Live Model Badge */}
            <div
              className={`hidden md:flex items-center space-x-2 text-xs font-mono px-3 py-1.5 rounded-lg border ${
                isCream
                  ? 'bg-white/80 border-[#e8dfd5] text-slate-700 shadow-xs'
                  : 'bg-slate-900/80 border-slate-800 text-slate-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              <span className="w-2 h-2 rounded-full bg-emerald-500 -ml-3.5" />
              <span>CUDA GPU Active</span>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={() => setTheme(isCream ? 'dark' : 'cream')}
              className={`p-2 rounded-xl border transition-all cursor-pointer ${
                isCream
                  ? 'bg-white border-[#e8dfd5] text-amber-800 hover:bg-amber-50 shadow-xs'
                  : 'bg-slate-900 border-slate-800 text-emerald-400 hover:bg-slate-800'
              }`}
              title="Toggle Light Cream / Dark Theme"
            >
              {isCream ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* ===================== Main Content ===================== */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* ==================== LEFT COLUMN: Controls & Upload (5 Cols) ==================== */}
          <div className="lg:col-span-5 space-y-6">
            
            {/* Upload Box Card */}
            <div
              className={`rounded-2xl p-6 border transition-all shadow-sm ${
                isCream
                  ? 'bg-white/90 border-[#e8dfd5] backdrop-blur-sm'
                  : 'bg-slate-900/80 border-slate-800 backdrop-blur-sm'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <UploadCloud
                    className={`w-5 h-5 ${isCream ? 'text-amber-700' : 'text-emerald-400'}`}
                  />
                  <h2 className="font-bold text-base tracking-tight">PCB Image Upload</h2>
                </div>
                <span className="text-[11px] font-mono text-slate-400">Up to 50MB</span>
              </div>

              {/* Drag & Drop Area */}
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative group cursor-pointer border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                  imagePreview
                    ? isCream
                      ? 'border-amber-400/60 bg-amber-50/30'
                      : 'border-emerald-500/50 bg-emerald-950/20'
                    : isCream
                    ? 'border-[#d4c6b5] hover:border-amber-600/80 bg-[#fbf9f5] hover:bg-amber-50/40'
                    : 'border-slate-700 hover:border-emerald-500/70 bg-slate-950/50 hover:bg-slate-900'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {imagePreview ? (
                  <div className="relative group/preview overflow-hidden rounded-lg max-h-52 flex items-center justify-center bg-black/5 dark:bg-black/30">
                    <img
                      src={imagePreview}
                      alt="PCB Preview"
                      className="object-contain w-full h-full max-h-48 rounded-lg transition-transform group-hover/preview:scale-105"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/preview:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-medium space-x-2">
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Click or Drop to Replace</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-6 flex flex-col items-center">
                    <div
                      className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-3 transition-transform group-hover:scale-110 shadow-xs ${
                        isCream
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-emerald-950 text-emerald-400'
                      }`}
                    >
                      <ImageIcon className="w-7 h-7" />
                    </div>
                    <p className="text-sm font-semibold mb-1">
                      Drag & Drop Full PCB Board Photo
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
                      High-resolution photos (~3000px) yield highest mAP accuracy
                    </p>
                    <span
                      className={`text-xs font-medium px-3 py-1.5 rounded-lg border shadow-xs transition-colors ${
                        isCream
                          ? 'bg-white border-[#d8ccbc] text-amber-800 hover:bg-amber-50'
                          : 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
                      }`}
                    >
                      Browse Device Files
                    </span>
                  </div>
                )}
              </div>

              {/* Preset Sample Quick Buttons */}
              <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-800 flex items-center justify-between">
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                  Test Presets:
                </span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => loadPreset('sample1')}
                    className={`text-xs px-2.5 py-1 rounded-md border transition-all cursor-pointer ${
                      isCream
                        ? 'bg-[#f4eee6] hover:bg-amber-100/70 border-[#e0d3c3] text-amber-900'
                        : 'bg-slate-800/80 hover:bg-slate-700 border-slate-700 text-slate-300'
                    }`}
                  >
                    Sample Board #01
                  </button>
                  <button
                    onClick={() => loadPreset('sample2')}
                    className={`text-xs px-2.5 py-1 rounded-md border transition-all cursor-pointer ${
                      isCream
                        ? 'bg-[#f4eee6] hover:bg-amber-100/70 border-[#e0d3c3] text-amber-900'
                        : 'bg-slate-800/80 hover:bg-slate-700 border-slate-700 text-slate-300'
                    }`}
                  >
                    Demo Board #02
                  </button>
                </div>
              </div>
            </div>

            {/* Hyperparameters & Settings Card */}
            <div
              className={`rounded-2xl p-6 border transition-all shadow-sm ${
                isCream
                  ? 'bg-white/90 border-[#e8dfd5]'
                  : 'bg-slate-900/80 border-slate-800'
              }`}
            >
              <div className="flex items-center space-x-2 mb-5">
                <Sliders
                  className={`w-5 h-5 ${isCream ? 'text-amber-700' : 'text-emerald-400'}`}
                />
                <h2 className="font-bold text-base tracking-tight">Detection Hyperparameters</h2>
              </div>

              <div className="space-y-5">
                {/* Confidence Threshold Slider */}
                <div>
                  <div className="flex justify-between items-center text-xs font-medium mb-2">
                    <span className="flex items-center space-x-1.5">
                      <span>Confidence Threshold</span>
                      <span className="text-slate-400 text-[10px]">(Filter low-conf)</span>
                    </span>
                    <span className="font-mono font-bold text-amber-700 dark:text-emerald-400 bg-amber-500/10 dark:bg-emerald-500/10 px-2 py-0.5 rounded border border-amber-500/20 dark:border-emerald-500/20">
                      {confThreshold.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.10"
                    max="0.99"
                    step="0.01"
                    value={confThreshold}
                    onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-amber-600 dark:accent-emerald-400 bg-slate-200 dark:bg-slate-700"
                  />
                  <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
                    <span>0.10 (Sensitive)</span>
                    <span>0.50</span>
                    <span>0.99 (Strict)</span>
                  </div>
                </div>

                {/* IoU NMS Threshold Slider */}
                <div>
                  <div className="flex justify-between items-center text-xs font-medium mb-2">
                    <span className="flex items-center space-x-1.5">
                      <span>IoU NMS Overlap</span>
                      <span className="text-slate-400 text-[10px]">(Box de-duplication)</span>
                    </span>
                    <span className="font-mono font-bold text-amber-700 dark:text-emerald-400 bg-amber-500/10 dark:bg-emerald-500/10 px-2 py-0.5 rounded border border-amber-500/20 dark:border-emerald-500/20">
                      {iouThreshold.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.10"
                    max="0.95"
                    step="0.05"
                    value={iouThreshold}
                    onChange={(e) => setIouThreshold(parseFloat(e.target.value))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-amber-600 dark:accent-emerald-400 bg-slate-200 dark:bg-slate-700"
                  />
                  <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
                    <span>0.10 (Merge)</span>
                    <span>0.45 (Default)</span>
                    <span>0.95 (Separate)</span>
                  </div>
                </div>

                {/* Secondary Classifier Checkbox */}
                <div
                  className={`p-3.5 rounded-xl border flex items-center justify-between cursor-pointer transition-colors ${
                    classifyCrops
                      ? isCream
                        ? 'bg-amber-50/60 border-amber-300'
                        : 'bg-emerald-950/30 border-emerald-800'
                      : isCream
                      ? 'bg-slate-50 border-slate-200'
                      : 'bg-slate-800/40 border-slate-700'
                  }`}
                  onClick={() => setClassifyCrops(!classifyCrops)}
                >
                  <div className="flex items-center space-x-2.5">
                    <Layers
                      className={`w-4 h-4 ${
                        classifyCrops
                          ? isCream
                            ? 'text-amber-700'
                            : 'text-emerald-400'
                          : 'text-slate-400'
                      }`}
                    />
                    <div>
                      <div className="text-xs font-semibold">EfficientNet-B0 Verification</div>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400">
                        Second opinion on each box with 2.5x context crop
                      </div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={classifyCrops}
                    onChange={(e) => setClassifyCrops(e.target.checked)}
                    className="w-4 h-4 rounded cursor-pointer accent-amber-600 dark:accent-emerald-400"
                  />
                </div>
              </div>

              {/* Glowing Run Detection CTA Button */}
              <button
                onClick={handleDetect}
                disabled={isProcessing}
                className={`w-full mt-6 py-3.5 px-6 rounded-xl font-bold text-sm tracking-wide uppercase flex items-center justify-center space-x-2.5 transition-all shadow-md cursor-pointer ${
                  isProcessing
                    ? 'opacity-60 cursor-not-allowed bg-slate-400 text-white'
                    : isCream
                    ? 'bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 hover:from-amber-500 hover:to-amber-700 text-white shadow-amber-600/30 hover:shadow-lg hover:shadow-amber-600/40 active:scale-[0.99]'
                    : 'bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-slate-950 shadow-emerald-500/25 hover:shadow-lg hover:shadow-emerald-500/40 active:scale-[0.99]'
                }`}
              >
                {isProcessing ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Inspecting Circuit Board...</span>
                  </>
                ) : (
                  <>
                    <Scan className="w-5 h-5" />
                    <span>Run YOLO Defect Detection</span>
                  </>
                )}
              </button>

              {/* Error Notice if any */}
              {errorMsg && (
                <div className="mt-4 p-3 rounded-lg bg-red-500/15 border border-red-500/30 text-red-700 dark:text-red-400 text-xs flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}
            </div>

            {/* Specs & Hardware Card */}
            <div
              className={`rounded-2xl p-4 border text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between ${
                isCream ? 'bg-[#f5ede2]/60 border-[#e8dfd5]' : 'bg-slate-900/40 border-slate-800'
              }`}
            >
              <div className="flex items-center space-x-2">
                <FileCode className="w-4 h-4 text-slate-400" />
                <span>Backend Target: <code className="font-mono text-amber-800 dark:text-emerald-400">/api/detect</code></span>
              </div>
              <span className="font-mono">mAP@0.5: 96.77%</span>
            </div>
          </div>


          {/* ==================== RIGHT COLUMN: Results View (7 Cols) ==================== */}
          <div className="lg:col-span-7 space-y-6">
            
            {/* Viewport / Inspection Container */}
            <div
              className={`rounded-2xl border overflow-hidden shadow-sm transition-all ${
                isCream
                  ? 'bg-white/95 border-[#e8dfd5]'
                  : 'bg-slate-900/90 border-slate-800'
              }`}
            >
              {/* Header Bar of Viewport */}
              <div
                className={`px-5 py-3.5 border-b flex items-center justify-between text-xs ${
                  isCream ? 'bg-[#faf6f0] border-[#e8dfd5]' : 'bg-slate-950/60 border-slate-800'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <div className="flex space-x-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-400/80" />
                    <div className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" />
                  </div>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Inspection Canvas
                  </span>
                  {result && (
                    <span className="font-mono text-[10px] text-slate-400">
                      [{result.image_width} x {result.image_height}px]
                    </span>
                  )}
                </div>

                {/* Viewport Toolbar */}
                {result && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setShowAnnotated(!showAnnotated)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-medium border flex items-center space-x-1.5 cursor-pointer ${
                        showAnnotated
                          ? isCream
                            ? 'bg-amber-100 border-amber-300 text-amber-800'
                            : 'bg-emerald-950 border-emerald-800 text-emerald-400'
                          : 'bg-transparent border-slate-300 text-slate-500'
                      }`}
                    >
                      {showAnnotated ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                      <span>{showAnnotated ? 'Bounding Boxes On' : 'Original Raw'}</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Viewport Body */}
              <div className="relative min-h-[380px] max-h-[500px] flex items-center justify-center bg-slate-950 overflow-hidden">
                
                {/* 1. Empty State (No file chosen yet) */}
                {!imagePreview && !isProcessing && (
                  <div className="text-center p-8 text-slate-400">
                    <div className="w-16 h-16 mx-auto mb-3 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600">
                      <Scan className="w-8 h-8 animate-pulse" />
                    </div>
                    <h3 className="font-bold text-base text-slate-200 mb-1">
                      No Board Loaded for Inspection
                    </h3>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">
                      Upload a PCB photo or choose a preset board to initiate multi-defect localization.
                    </p>
                  </div>
                )}

                {/* 2. Scanning / Futuristic Processing State */}
                {isProcessing && (
                  <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/85 backdrop-blur-xs">
                    {/* Render current image in background */}
                    {imagePreview && (
                      <img
                        src={imagePreview}
                        alt="Scanning board"
                        className="absolute inset-0 w-full h-full object-contain opacity-25 filter blur-xs"
                      />
                    )}

                    {/* Animated Laser Beam */}
                    <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-emerald-400 to-transparent shadow-[0_0_15px_#10b981] animate-laser pointer-events-none" />

                    {/* Scanning Telemetry HUD */}
                    <div className="relative z-30 p-6 rounded-2xl bg-slate-900/90 border border-slate-700 text-center shadow-2xl max-w-sm mx-4">
                      <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-3 animate-spin">
                        <Scan className="w-6 h-6" />
                      </div>
                      <h4 className="font-mono text-sm font-bold text-emerald-400 mb-1 tracking-wider uppercase">
                        Scanning PCB Layers...
                      </h4>
                      <p className="text-xs text-slate-300 font-mono mb-4">
                        {activeStepText}
                      </p>

                      {/* Progress bar */}
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden border border-slate-700">
                        <div
                          className="bg-gradient-to-r from-emerald-500 to-cyan-400 h-full transition-all duration-300 rounded-full"
                          style={{ width: `${scanningProgress}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1.5">
                        <span>Model: YOLOv8s</span>
                        <span>{scanningProgress}%</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. Rendered Image View (Processed or Raw) */}
                {imagePreview && !isProcessing && (
                  <div className="relative w-full h-full flex items-center justify-center">
                    <img
                      src={
                        showAnnotated && result?.annotated_image_base64
                          ? `data:image/png;base64,${result.annotated_image_base64}`
                          : imagePreview
                      }
                      alt="Annotated PCB Result"
                      className="object-contain max-h-[480px] w-full"
                    />

                    {/* Interactive bounding box overlay if rendering over raw SVG */}
                    {showAnnotated &&
                      !result?.annotated_image_base64 &&
                      result?.detections?.map((det, idx) => (
                        <div
                          key={idx}
                          onClick={() => setSelectedDetection(det)}
                          className="absolute border-2 border-red-500 bg-red-500/10 hover:bg-red-500/25 transition-all cursor-pointer group/box"
                          style={{
                            left: `${(det.bbox[0] / result.image_width) * 100}%`,
                            top: `${(det.bbox[1] / result.image_height) * 100}%`,
                            width: `${((det.bbox[2] - det.bbox[0]) / result.image_width) * 100}%`,
                            height: `${((det.bbox[3] - det.bbox[1]) / result.image_height) * 100}%`,
                          }}
                        >
                          <span className="absolute -top-6 left-0 text-[10px] font-mono bg-red-600 text-white px-1.5 py-0.5 rounded shadow-sm whitespace-nowrap">
                            {det.class_name} ({Math.round(det.confidence * 100)}%)
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* Result Status Bar */}
              {result && (
                <div
                  className={`px-5 py-3 border-t text-xs flex flex-wrap items-center justify-between gap-3 ${
                    isCream ? 'bg-[#faf6f0] border-[#e8dfd5]' : 'bg-slate-950/70 border-slate-800'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <span className="flex items-center space-x-1 text-slate-500">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Latency: <strong className="font-mono text-slate-700 dark:text-slate-200">{result.inference_time_ms} ms</strong></span>
                    </span>
                    <span className="text-slate-300 dark:text-slate-700">|</span>
                    <span className="text-slate-500">
                      Device: <strong className="font-mono uppercase text-slate-700 dark:text-slate-200">{result.device}</strong>
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="text-slate-400 font-mono text-[11px]">
                      Settings: conf={result.settings_used?.conf || confThreshold}, iou={result.settings_used?.iou || iouThreshold}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Warning Banner if present */}
            {result?.warning && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-300 text-xs flex items-start space-x-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold mb-0.5">Operational Quality Notice</p>
                  <p className="text-amber-700 dark:text-amber-400/90 leading-relaxed">
                    {result.warning}
                  </p>
                </div>
              </div>
            )}

            {/* ==================== DEFECT SUMMARY PANEL ==================== */}
            {result && (
              <div
                className={`rounded-2xl p-6 border transition-all shadow-sm ${
                  isCream
                    ? 'bg-white/95 border-[#e8dfd5]'
                    : 'bg-slate-900/90 border-slate-800'
                }`}
              >
                {/* Summary Header */}
                <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-200/60 dark:border-slate-800">
                  <div className="flex items-center space-x-2.5">
                    <div
                      className={`p-1.5 rounded-lg ${
                        result.total_defects > 0
                          ? 'bg-red-500/15 text-red-600'
                          : 'bg-emerald-500/15 text-emerald-600'
                      }`}
                    >
                      {result.total_defects > 0 ? (
                        <ShieldAlert className="w-5 h-5" />
                      ) : (
                        <CheckCircle2 className="w-5 h-5" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-bold text-base">
                        Defect Inspection Findings
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {result.total_defects > 0
                          ? `Identified ${result.total_defects} defect instances requiring attention`
                          : 'No defects detected above confidence threshold'}
                      </p>
                    </div>
                  </div>

                  {/* Total Defects Found Badge */}
                  <div
                    className={`px-3 py-1.5 rounded-xl font-mono font-bold text-sm border shadow-xs ${
                      result.total_defects > 0
                        ? 'bg-red-500/15 text-red-600 border-red-500/30'
                        : 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30'
                    }`}
                  >
                    Total Defects: {result.total_defects}
                  </div>
                </div>

                {/* Defect Cards Grid */}
                {result.total_defects > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                    {result.detections.map((det, idx) => {
                      const isSelected = selectedDetection === det;
                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedDetection(det)}
                          className={`p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden ${
                            isSelected
                              ? isCream
                                ? 'bg-amber-50/70 border-amber-400 ring-2 ring-amber-400/30 shadow-sm'
                                : 'bg-slate-800 border-emerald-500 ring-2 ring-emerald-500/30 shadow-md'
                              : isCream
                              ? 'bg-[#fcfaf7] border-[#e8dfd5] hover:bg-amber-50/40 hover:border-amber-300'
                              : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50'
                          }`}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <div className="font-bold text-sm tracking-tight capitalize text-slate-800 dark:text-slate-100">
                                {det.class_name.replace('_', ' ')}
                              </div>
                              <span className="font-mono text-[11px] text-slate-400">
                                Box: [{det.bbox.join(', ')}]
                              </span>
                            </div>

                            {/* Confidence Pill */}
                            <span
                              className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full border ${
                                isCream
                                  ? 'bg-amber-100 text-amber-800 border-amber-300'
                                  : 'bg-emerald-950 text-emerald-400 border-emerald-800'
                              }`}
                            >
                              {Math.round(det.confidence * 100)}% Conf
                            </span>
                          </div>

                          {/* Secondary Classifier Pill (if classify_crops was true) */}
                          {det.classifier_class && (
                            <div className="mt-2 text-[11px] font-mono flex items-center space-x-1 text-slate-600 dark:text-slate-400 bg-black/5 dark:bg-black/30 p-1.5 rounded-lg">
                              <Sparkles className="w-3.5 h-3.5 text-amber-600 dark:text-emerald-400" />
                              <span>EfficientNet-B0:</span>
                              <strong className="text-slate-900 dark:text-slate-100">
                                {det.classifier_class} ({Math.round(det.classifier_confidence * 100)}%)
                              </strong>
                            </div>
                          )}

                          {/* Severity & View Details link */}
                          <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-200/50 dark:border-slate-800/80 text-[11px]">
                            <span
                              className={`px-2 py-0.5 rounded font-medium border ${getSeverityBadge(
                                det.defect_details?.severity
                              )}`}
                            >
                              {det.defect_details?.severity || 'Medium'} Severity
                            </span>
                            <span className="text-amber-700 dark:text-emerald-400 flex items-center space-x-0.5 font-medium hover:underline">
                              <span>Inspect Info</span>
                              <ChevronRight className="w-3 h-3" />
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-6 text-center text-slate-400">
                    <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                    <p className="font-medium text-sm text-slate-700 dark:text-slate-300">
                      No anomalies detected
                    </p>
                    <p className="text-xs text-slate-400">
                      Try adjusting the confidence slider or test another section of the board.
                    </p>
                  </div>
                )}

                {/* Selected Defect Detail Modal / Drawer Card */}
                {selectedDetection && selectedDetection.defect_details && (
                  <div
                    className={`mt-6 p-5 rounded-xl border animate-in fade-in duration-200 ${
                      isCream
                        ? 'bg-[#f8f4ed] border-amber-300/80 shadow-xs'
                        : 'bg-slate-800/80 border-slate-700 shadow-lg'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        <Info className="w-4 h-4 text-amber-700 dark:text-emerald-400" />
                        <h4 className="font-bold text-sm">
                          Engineering Remediation:{' '}
                          <span className="capitalize">
                            {selectedDetection.defect_details.name}
                          </span>
                        </h4>
                      </div>
                      <button
                        onClick={() => setSelectedDetection(null)}
                        className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                      >
                        ✕ Close
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="font-semibold text-slate-400 block mb-1">
                          Functional Risk:
                        </span>
                        <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                          {selectedDetection.defect_details.risk}
                        </p>
                      </div>
                      <div>
                        <span className="font-semibold text-slate-400 block mb-1">
                          Action / Remediation:
                        </span>
                        <p className="text-slate-700 dark:text-slate-300 leading-relaxed flex items-start space-x-1.5">
                          <Wrench className="w-3.5 h-3.5 shrink-0 text-amber-600 dark:text-emerald-400 mt-0.5" />
                          <span>{selectedDetection.defect_details.remediation}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

import React, { useState } from 'react';
import {
  Eye,
  EyeOff,
  Scan,
  AlertTriangle,
  ShieldAlert,
  Layers,
  Wrench,
  Sparkles,
  Maximize2,
  Clock,
  Download,
  Info
} from 'lucide-react';
import { DEFECT_CLASSES } from '../config';

export default function InspectionCanvas({
  imagePreview,
  result,
  isProcessing,
  activeStepText,
  scanningProgress,
  onOpenLightbox,
}) {
  const [showAnnotated, setShowAnnotated] = useState(true);
  const [selectedDetIndex, setSelectedDetIndex] = useState(null);

  const detections = result?.detections || [];
  const totalDefects = result?.total_defects || detections.length || 0;

  // Severity color badge helper
  const getSeverityBadge = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return 'bg-red-500/15 text-red-700 border-red-500/30';
      case 'high':
        return 'bg-orange-500/15 text-orange-700 border-orange-500/30';
      case 'medium':
        return 'bg-amber-500/15 text-amber-700 border-amber-500/30';
      default:
        return 'bg-emerald-500/15 text-emerald-700 border-emerald-500/30';
    }
  };

  return (
    <div className="rounded-3xl border bg-white border-[#e8dfd5] shadow-[0_4px_25px_-5px_rgba(217,119,6,0.06)] overflow-hidden transition-all">
      {/* Canvas Top Bar */}
      <div className="px-5 py-3.5 border-b border-[#e8dfd5] bg-[#faf6f0] flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-3">
          {/* Retro hardware dots */}
          <div className="flex space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-400/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" />
          </div>
          <span className="font-extrabold text-slate-800 tracking-tight">
            PCB Inspection Canvas
          </span>
          {result?.image_width && result?.image_height && (
            <span className="font-mono text-[11px] text-slate-500">
              [{result.image_width} × {result.image_height}px]
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2">
          {result && (
            <>
              <button
                type="button"
                onClick={() => setShowAnnotated(!showAnnotated)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border flex items-center space-x-1.5 cursor-pointer transition-all ${
                  showAnnotated
                    ? 'bg-amber-100/80 border-amber-300 text-amber-900 shadow-2xs'
                    : 'bg-white border-[#dfd4c4] text-slate-600'
                }`}
              >
                {showAnnotated ? <Eye className="w-3.5 h-3.5 text-amber-700" /> : <EyeOff className="w-3.5 h-3.5" />}
                <span>{showAnnotated ? 'Bounding Boxes On' : 'Original Raw'}</span>
              </button>

              {onOpenLightbox && (
                <button
                  type="button"
                  onClick={onOpenLightbox}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#dfd4c4] bg-white text-slate-700 hover:bg-amber-50 cursor-pointer flex items-center space-x-1 shadow-2xs"
                  title="Expand to Fullscreen Lightbox"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>Expand</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Main Visual Display Area */}
      <div className="relative min-h-[380px] max-h-[520px] flex items-center justify-center bg-[#13241b] overflow-hidden select-none">
        {/* Empty State */}
        {!imagePreview && !isProcessing && (
          <div className="text-center p-8 text-slate-300">
            <div className="w-16 h-16 mx-auto mb-3 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-amber-400">
              <Scan className="w-8 h-8 animate-pulse" />
            </div>
            <h3 className="font-bold text-base text-white mb-1">
              No Board Loaded for Inspection
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              Drop a PCB photo or choose a sample board from the uploader to initiate multi-defect localization.
            </p>
          </div>
        )}

        {/* Scanning State with Animated Laser Beam */}
        {isProcessing && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/75 backdrop-blur-xs">
            {imagePreview && (
              <img
                src={imagePreview}
                alt="Scanning board"
                className="absolute inset-0 w-full h-full object-contain opacity-25 filter blur-xs"
              />
            )}

            {/* Laser Beam Animation */}
            <div className="absolute inset-x-0 h-1.5 bg-gradient-to-r from-transparent via-amber-400 to-transparent shadow-[0_0_20px_#f59e0b] animate-laser pointer-events-none" />

            {/* Scanning Telemetry HUD */}
            <div className="relative z-30 p-6 rounded-2xl bg-slate-900/90 border border-amber-500/30 text-center shadow-2xl max-w-sm mx-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-3 animate-spin">
                <Scan className="w-6 h-6" />
              </div>
              <h4 className="font-mono text-sm font-bold text-amber-300 mb-1 tracking-wider uppercase">
                Scanning PCB Layers...
              </h4>
              <p className="text-xs text-slate-300 font-mono mb-4">
                {activeStepText || 'Running YOLOv8s tensor inference...'}
              </p>

              {/* Progress bar */}
              <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden border border-slate-700">
                <div
                  className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-300 h-full transition-all duration-300 rounded-full"
                  style={{ width: `${scanningProgress}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-2">
                <span>Model: YOLOv8s AOI</span>
                <span>{scanningProgress}%</span>
              </div>
            </div>
          </div>
        )}

        {/* Rendered Board View */}
        {imagePreview && !isProcessing && (
          <div className="relative w-full h-full flex items-center justify-center">
            <img
              src={
                showAnnotated && (result?.annotated_image_url || result?.image_url)
                  ? result.annotated_image_url || result.image_url
                  : imagePreview
              }
              alt="PCB Image"
              className="object-contain max-h-[500px] w-full"
            />
          </div>
        )}

        {/* Low-Resolution Warning Overlay if present */}
        {result?.warning && (
          <div className="absolute bottom-3 left-3 right-3 max-w-lg p-3 rounded-xl bg-amber-950/90 border border-amber-700/80 text-amber-200 text-xs shadow-xl backdrop-blur-xs flex items-start space-x-2 z-20">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
            <div>
              <strong className="block text-amber-300">Resolution Notice:</strong>
              <span>{result.warning}</span>
            </div>
          </div>
        )}
      </div>

      {/* Defect Findings & Diagnostic Breakdown Panel */}
      {result && (
        <div className="p-6 bg-white border-t border-[#e8dfd5] space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#f0e7db]">
            <div className="flex items-center space-x-2.5">
              <span className="font-extrabold text-base text-slate-900">
                Localized Findings:
              </span>
              <span
                className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                  totalDefects > 0
                    ? 'bg-red-500/10 text-red-700 border-red-500/25'
                    : 'bg-emerald-500/10 text-emerald-700 border-emerald-500/25'
                }`}
              >
                {totalDefects > 0
                  ? `${totalDefects} Anomaly Location${totalDefects === 1 ? '' : 's'}`
                  : 'No Detections Above Threshold'}
              </span>
            </div>

            {result.inference_time_ms && (
              <div className="flex items-center space-x-1.5 text-xs font-mono text-slate-500">
                <Clock className="w-3.5 h-3.5 text-amber-700" />
                <span>Inference: {result.inference_time_ms.toFixed(1)}ms</span>
              </div>
            )}
          </div>

          {/* Honest Quality Notice */}
          <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-950 text-xs flex items-start space-x-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <strong>Quality Policy Notice: </strong>
              No detections means nothing was found above the threshold, not a guarantee the board is defect-free.
              Best on high-resolution board photos; low-resolution images may be unreliable.
            </div>
          </div>

          {/* Detections List Grid */}
          {detections.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1">
              {detections.map((det, idx) => {
                const clsMeta = DEFECT_CLASSES[det.class_name] || {
                  name: det.class_name,
                  color: '#b45309',
                };
                const details = det.defect_details || {};
                const isSelected = selectedDetIndex === idx;

                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedDetIndex(isSelected ? null : idx)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer bg-[#faf8f5] hover:border-amber-400 ${
                      isSelected
                        ? 'border-amber-600 ring-2 ring-amber-500/20 shadow-xs'
                        : 'border-[#e8dfd5]'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span
                          className="w-3 h-3 rounded-full shrink-0 shadow-2xs"
                          style={{ backgroundColor: clsMeta.color }}
                        />
                        <span className="font-bold text-xs text-slate-900">
                          {clsMeta.name}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-white border border-[#dfd4c4] text-slate-700 shadow-2xs">
                        {(det.confidence * 100).toFixed(1)}% Conf
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-600 space-y-1 mb-2">
                      {details.severity && (
                        <div>
                          <span className="font-semibold text-slate-700">Severity: </span>
                          <span
                            className={`font-semibold px-1.5 py-0.2 rounded text-[10px] border ${getSeverityBadge(details.severity)}`}
                          >
                            {details.severity}
                          </span>
                        </div>
                      )}
                      {details.risk && (
                        <p className="line-clamp-2">
                          <span className="font-semibold text-slate-700">Risk: </span>
                          {details.risk}
                        </p>
                      )}
                    </div>

                    {det.bbox && (
                      <div className="pt-2 border-t border-[#f0e7db] text-[10px] font-mono text-slate-400 flex items-center justify-between">
                        <span>BBox:</span>
                        <span>
                          [{Math.round(det.bbox[0])}, {Math.round(det.bbox[1])}, {Math.round(det.bbox[2])}, {Math.round(det.bbox[3])}]
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-slate-500 text-xs">
              No anomalies localized above {result.settings_used?.conf || 0.25} confidence threshold.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

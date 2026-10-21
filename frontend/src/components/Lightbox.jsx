import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  Eye,
  EyeOff,
  AlertTriangle,
  Info,
  Wrench,
  Sparkles,
  Maximize2
} from 'lucide-react';
import { DEFECT_CLASSES } from '../config';

export default function Lightbox({
  image,
  images = [],
  currentIndex = 0,
  onClose,
  onNavigate,
}) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedDet, setSelectedDet] = useState(null);

  // Reset zoom & pan when image changes
  useEffect(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
    setSelectedDet(null);
  }, [image]);

  // Keyboard navigation listener (ArrowLeft, ArrowRight, Escape)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowLeft') {
        if (images.length > 1) {
          const prevIdx = (currentIndex - 1 + images.length) % images.length;
          onNavigate(images[prevIdx], prevIdx);
        }
      } else if (e.key === 'ArrowRight') {
        if (images.length > 1) {
          const nextIdx = (currentIndex + 1) % images.length;
          onNavigate(images[nextIdx], nextIdx);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentIndex, images, onClose, onNavigate]);

  if (!image) return null;

  // Zoom controls
  const zoomIn = () => setScale((s) => Math.min(s + 0.35, 4));
  const zoomOut = () =>
    setScale((s) => {
      const next = Math.max(s - 0.35, 1);
      if (next === 1) setPosition({ x: 0, y: 0 });
      return next;
    });
  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  // Pan dragging
  const handleMouseDown = (e) => {
    if (scale > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging && scale > 1) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  // Download this image
  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = image.image_url || image.thumb_url;
    link.download = `annotated_${image.filename || 'pcb_image.jpg'}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const detections = image.detections || [];
  const totalDefects = image.total_defects || 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Detailed Inspection: ${image.filename}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md transition-all animate-in fade-in duration-200"
    >
      {/* Lightbox Container */}
      <div className="relative w-full h-full max-w-7xl max-h-screen p-4 sm:p-6 flex flex-col justify-between">
        {/* Top Control Bar */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-700/80 text-white z-20">
          <div className="flex items-center space-x-3">
            <span className="font-mono font-bold text-sm sm:text-base truncate max-w-xs sm:max-w-md">
              {image.filename}
            </span>
            <span className="text-xs font-mono text-slate-400">
              ({currentIndex + 1} of {images.length}) • {image.width}x{image.height}px
            </span>
          </div>

          <div className="flex items-center space-x-2">
            {/* Zoom toolbar */}
            <div className="hidden sm:flex items-center space-x-1 bg-slate-900/80 rounded-lg p-1 border border-slate-700 text-slate-300">
              <button
                onClick={zoomOut}
                disabled={scale <= 1}
                className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-[11px] font-mono px-2">{Math.round(scale * 100)}%</span>
              <button
                onClick={zoomIn}
                disabled={scale >= 4}
                className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={resetZoom}
                className="p-1.5 rounded hover:bg-slate-800 cursor-pointer text-slate-400 hover:text-white"
                title="Reset Zoom (1:1)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            </div>

            {/* Toggle bounding boxes */}
            <button
              onClick={() => setShowBoxes(!showBoxes)}
              className={`p-2 rounded-lg border text-xs flex items-center space-x-1.5 cursor-pointer ${
                showBoxes
                  ? 'bg-emerald-950 border-emerald-800 text-emerald-400'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
              title="Toggle Boxes"
            >
              {showBoxes ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              <span className="hidden sm:inline">{showBoxes ? 'Boxes' : 'Raw'}</span>
            </button>

            {/* Download */}
            <button
              onClick={handleDownload}
              className="p-2 rounded-lg border border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 cursor-pointer flex items-center space-x-1 text-xs"
              title="Download Annotated Image"
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Export</span>
            </button>

            {/* Close */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg border border-slate-700 bg-slate-900 hover:bg-red-950/50 hover:border-red-800 hover:text-red-400 text-slate-400 cursor-pointer"
              title="Close Lightbox (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Main Canvas Area */}
        <div
          className="relative flex-1 my-3 overflow-hidden rounded-xl bg-slate-950 flex items-center justify-center cursor-grab active:cursor-grabbing select-none"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Navigation Arrows */}
          {images.length > 1 && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const prevIdx = (currentIndex - 1 + images.length) % images.length;
                  onNavigate(images[prevIdx], prevIdx);
                }}
                className="absolute left-4 z-30 p-3 rounded-full bg-slate-900/80 hover:bg-slate-800 text-white border border-slate-700/80 shadow-lg cursor-pointer backdrop-blur-xs transition-transform hover:scale-110"
                title="Previous Image (Arrow Left)"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const nextIdx = (currentIndex + 1) % images.length;
                  onNavigate(images[nextIdx], nextIdx);
                }}
                className="absolute right-4 z-30 p-3 rounded-full bg-slate-900/80 hover:bg-slate-800 text-white border border-slate-700/80 shadow-lg cursor-pointer backdrop-blur-xs transition-transform hover:scale-110"
                title="Next Image (Arrow Right)"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            </>
          )}

          {/* Image & Interactive Transform */}
          <div
            className="w-full h-full flex items-center justify-center transition-transform duration-75"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            }}
          >
            <img
              src={
                showBoxes && image.image_url
                  ? image.image_url
                  : image.thumb_url || image.image_url
              }
              alt={image.filename}
              className="max-h-full max-w-full object-contain pointer-events-none"
              draggable={false}
            />
          </div>

          {/* Warning Banner Overlay if Low-Res or Warning */}
          {image.warning && (
            <div className="absolute bottom-4 left-4 right-4 sm:left-auto sm:right-4 max-w-md p-3.5 rounded-xl bg-amber-950/90 border border-amber-800 text-amber-300 text-xs shadow-xl backdrop-blur-sm flex items-start space-x-2.5 z-20">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <span className="font-bold block">Resolution Notice:</span>
                <span className="text-amber-200/90 leading-relaxed">{image.warning}</span>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Drawer: Defect Findings & Coordinates */}
        <div className="max-h-56 overflow-y-auto rounded-xl bg-slate-900/95 border border-slate-800 p-4 text-white z-20">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm">Detected Defects:</span>
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full border ${
                  totalDefects > 0
                    ? 'bg-red-500/15 text-red-400 border-red-500/30'
                    : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                }`}
              >
                {totalDefects > 0 ? `${totalDefects} Findings` : 'No Detections Above Threshold'}
              </span>
            </div>

            <span className="text-[11px] font-mono text-slate-400">
              Navigate: [←] / [→] keys • Close: [Esc]
            </span>
          </div>

          {totalDefects > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {detections.map((det, idx) => {
                const classMeta = DEFECT_CLASSES[det.class_name] || {
                  color: '#94a3b8',
                  name: det.class_name,
                };
                const isSelected = selectedDet === det;

                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedDet(isSelected ? null : det)}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-slate-800 border-emerald-500 ring-1 ring-emerald-500'
                        : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center space-x-1.5">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: classMeta.color }}
                        />
                        <strong className="capitalize text-slate-100">{classMeta.name}</strong>
                      </div>
                      <span className="font-mono text-emerald-400 font-bold">
                        {Math.round(det.confidence * 100)}%
                      </span>
                    </div>

                    <div className="font-mono text-[10px] text-slate-400">
                      BBox: [{det.bbox?.join(', ')}]
                    </div>

                    {det.classifier_class && (
                      <div className="mt-1 text-[10px] font-mono text-slate-300 flex items-center space-x-1">
                        <Sparkles className="w-3 h-3 text-amber-400" />
                        <span>Classifier: {det.classifier_class}</span>
                      </div>
                    )}

                    {isSelected && det.defect_details && (
                      <div className="mt-2 pt-2 border-t border-slate-700 text-[11px] text-slate-300 space-y-1">
                        <div>
                          <span className="text-slate-400 font-semibold">Risk: </span>
                          {det.defect_details.risk}
                        </div>
                        <div>
                          <span className="text-slate-400 font-semibold">Remediation: </span>
                          {det.defect_details.remediation}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">
              No defects detected above the confidence threshold for this board photo.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

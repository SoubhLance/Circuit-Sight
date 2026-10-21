import React from 'react';
import { Cpu, ArrowRight, Zap, ShieldCheck, Layers, Gauge, Sparkles } from 'lucide-react';

export default function Hero({ onLaunchInspector, onLearnMore }) {
  return (
    <section className="relative overflow-hidden py-16 sm:py-24 border-b border-[#e8dfd5] bg-gradient-to-b from-[#faf7f2] via-[#f7f2ea] to-[#f4ece0]">
      {/* Decorative background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-gradient-to-tr from-amber-400/15 via-orange-300/15 to-emerald-400/10 blur-3xl pointer-events-none rounded-full" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
        {/* Subtle pill tag */}
        <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-xs font-mono font-semibold mb-6 border bg-amber-500/10 border-amber-600/25 text-amber-900 shadow-xs backdrop-blur-xs">
          <span className="w-2 h-2 rounded-full bg-amber-600 animate-pulse" />
          <span>Industrial Deep Learning AOI Inspection</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[#1e293b] max-w-4xl mx-auto leading-tight">
          High-Yield Industrial PCB Defect Localization with{' '}
          <span className="bg-gradient-to-r from-amber-700 via-amber-800 to-amber-950 bg-clip-text text-transparent">
            CircuitSight
          </span>
        </h1>

        {/* One-Line Value Proposition */}
        <p className="mt-6 text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed font-normal">
          Real-time multi-defect detection and automated folder batch inspection across manufacturing layers using fine-tuned YOLOv8 and EfficientNet.
        </p>

        {/* CTA Launch Button */}
        <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onLaunchInspector}
            className="w-full sm:w-auto px-9 py-4 rounded-xl font-bold text-sm tracking-wide text-white uppercase flex items-center justify-center space-x-3 transition-all shadow-lg cursor-pointer bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 hover:from-amber-700 hover:to-amber-900 shadow-amber-700/25 hover:shadow-xl hover:shadow-amber-700/35 hover:-translate-y-0.5 active:translate-y-0 active:scale-95"
          >
            <Cpu className="w-5 h-5 text-amber-200" />
            <span>Inspect Boards</span>
            <ArrowRight className="w-4 h-4 text-amber-200" />
          </button>

          <button
            onClick={onLearnMore}
            className="w-full sm:w-auto px-7 py-4 rounded-xl font-semibold text-sm border transition-all cursor-pointer bg-white/90 hover:bg-white text-slate-700 border-[#d8ccbc] shadow-xs hover:border-amber-400"
          >
            View Defect Taxonomy
          </button>
        </div>

        {/* Telemetry Metrics Bar */}
        <div className="mt-14 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto text-left">
          <div className="p-4 rounded-xl border bg-white/90 border-[#e8dfd5] shadow-xs hover:border-amber-400 transition-colors">
            <div className="flex items-center space-x-2 text-slate-500 mb-1">
              <Gauge className="w-4 h-4 text-amber-700" />
              <span className="text-[11px] font-mono uppercase tracking-wider">mAP@0.5</span>
            </div>
            <div className="text-xl font-extrabold font-mono text-slate-900">
              96.77%
            </div>
          </div>

          <div className="p-4 rounded-xl border bg-white/90 border-[#e8dfd5] shadow-xs hover:border-amber-400 transition-colors">
            <div className="flex items-center space-x-2 text-slate-500 mb-1">
              <Zap className="w-4 h-4 text-amber-700" />
              <span className="text-[11px] font-mono uppercase tracking-wider">Resolution</span>
            </div>
            <div className="text-xl font-extrabold font-mono text-slate-900">
              1024px Full
            </div>
          </div>

          <div className="p-4 rounded-xl border bg-white/90 border-[#e8dfd5] shadow-xs hover:border-amber-400 transition-colors">
            <div className="flex items-center space-x-2 text-slate-500 mb-1">
              <Layers className="w-4 h-4 text-amber-700" />
              <span className="text-[11px] font-mono uppercase tracking-wider">Architecture</span>
            </div>
            <div className="text-xl font-extrabold font-mono text-slate-900">
              YOLOv8s AOI
            </div>
          </div>

          <div className="p-4 rounded-xl border bg-white/90 border-[#e8dfd5] shadow-xs hover:border-amber-400 transition-colors">
            <div className="flex items-center space-x-2 text-slate-500 mb-1">
              <ShieldCheck className="w-4 h-4 text-amber-700" />
              <span className="text-[11px] font-mono uppercase tracking-wider">Batch Capacity</span>
            </div>
            <div className="text-xl font-extrabold font-mono text-slate-900">
              Auto-Chunks 50
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

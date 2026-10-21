import React, { useState, useEffect } from 'react';
import { Cpu, FileCode, ExternalLink, ShieldCheck, Database, Layers } from 'lucide-react';
import { API_BASE_URL } from '../config';

export default function Footer() {
  const [healthData, setHealthData] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setHealthData(data))
      .catch(() => setHealthData(null));
  }, []);

  const device = healthData?.device || 'CUDA GPU';
  const modelName = healthData?.detector?.model_name || 'yolov8s';
  const map50 = healthData?.detector?.map50 ? (healthData.detector.map50 * 100).toFixed(2) : '96.77';

  return (
    <footer className="mt-20 border-t border-[#e8dfd5] bg-[#f7f2ea]/90 backdrop-blur-md transition-colors text-xs text-slate-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8 pb-8 border-b border-[#e8dfd5]">
          {/* Brand & Purpose */}
          <div className="space-y-2 md:col-span-2">
            <div className="flex items-center space-x-2">
              <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-800 border border-amber-500/25">
                <Cpu className="w-4 h-4" />
              </div>
              <span className="font-extrabold text-base tracking-tight text-slate-900">
                CircuitSight AOI
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed max-w-sm">
              Detector-first automated optical inspection system providing real-time bounding box localization and secondary classification for industrial printed circuit board fabrication.
            </p>
          </div>

          {/* Model & Diagnostics */}
          <div className="space-y-1.5">
            <span className="font-bold uppercase tracking-wider text-[11px] text-slate-800 block mb-2">
              Model Diagnostics
            </span>
            <div className="flex items-center space-x-1.5">
              <Layers className="w-3.5 h-3.5 text-amber-700" />
              <span>Primary: <strong className="font-mono text-slate-800">{modelName}</strong></span>
            </div>
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-700" />
              <span>Validation: <strong className="font-mono text-slate-800">mAP@0.5 {map50}%</strong></span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-amber-700" />
              <span>Compute: <strong className="font-mono uppercase text-slate-800">{device}</strong></span>
            </div>
          </div>

          {/* API Endpoints & Links */}
          <div className="space-y-1.5">
            <span className="font-bold uppercase tracking-wider text-[11px] text-slate-800 block mb-2">
              API Documentation
            </span>
            <div>
              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                className="hover:text-amber-800 flex items-center space-x-1 transition-colors"
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>Swagger Interactive Docs (/docs)</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <a
                href="/redoc"
                target="_blank"
                rel="noreferrer"
                className="hover:text-amber-800 flex items-center space-x-1 transition-colors"
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>ReDoc API Reference (/redoc)</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <a
                href="/api/health"
                target="_blank"
                rel="noreferrer"
                className="hover:text-amber-800 flex items-center space-x-1 transition-colors"
              >
                <span>System Health Telemetry (/api/health)</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Bottom copyright & IPC disclaimer */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-500">
          <div>
            CircuitSight Deep Learning Optical Inspection Service • IPC-A-600 Standards
          </div>
          <div className="font-mono">
            FastAPI Backend • PyTorch {healthData ? 'Active' : 'Standby'}
          </div>
        </div>
      </div>
    </footer>
  );
}

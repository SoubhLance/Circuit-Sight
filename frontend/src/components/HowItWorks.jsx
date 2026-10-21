import React from 'react';
import { UploadCloud, Scan, FileArchive, CheckCircle2 } from 'lucide-react';
import { DEFECT_CLASSES } from '../config';

export default function HowItWorks() {
  const steps = [
    {
      number: '01',
      title: 'Upload Images or Folder',
      description:
        'Select single PCB images, multi-select several files, or drag & drop an entire folder hierarchy. Non-image files are automatically filtered out.',
      icon: UploadCloud,
    },
    {
      number: '02',
      title: 'YOLOv8 Defect Localization',
      description:
        'GPU-accelerated tensor inference detects 6 defect classes with high-precision bounding boxes. Auto-splits large folders into chunks of 50 to maximize throughput.',
      icon: Scan,
    },
    {
      number: '03',
      title: 'Review & Consolidated Export',
      description:
        'Inspect results via interactive canvas and full-resolution lightbox with zoom/pan. Download consolidated ZIP archives and CSV reports for manufacturing QA.',
      icon: FileArchive,
    },
  ];

  return (
    <section id="how-it-works" className="py-16 sm:py-20 border-b border-[#e8dfd5] bg-[#faf7f2]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-14">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-amber-700 mb-2">
            Inspection Workflow
          </h2>
          <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            How CircuitSight Operates
          </h3>
          <p className="mt-3 text-sm text-slate-600">
            A three-stage detector-first optical inspection pipeline designed for high-density surface mount and through-hole PCB assembly verification.
          </p>
        </div>

        {/* 3 Step Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.number}
                className="relative rounded-2xl p-6 border bg-white border-[#e8dfd5] shadow-xs hover:shadow-md hover:border-amber-400 transition-all group"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="p-3 rounded-xl bg-amber-500/10 text-amber-800 border border-amber-500/20 group-hover:scale-105 transition-transform">
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className="text-2xl font-mono font-black text-slate-300">
                    {step.number}
                  </span>
                </div>
                <h4 className="font-bold text-base text-slate-900 mb-2">
                  {step.title}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Taxonomy Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <h3 className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900">
            Industrial PCB Defect Taxonomy
          </h3>
          <p className="mt-2 text-xs text-slate-500">
            The 6 standard manufacturing defect classes localized by CircuitSight. Fixed colors are maintained throughout legends, badges, and bounding boxes.
          </p>
        </div>

        {/* 6 Defect Classes Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.values(DEFECT_CLASSES).map((item) => (
            <div
              key={item.id}
              className="rounded-xl p-5 border bg-white border-[#e8dfd5] shadow-xs hover:border-amber-400 hover:shadow-sm transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center space-x-2">
                    <span
                      className="w-3.5 h-3.5 rounded-full shrink-0 shadow-xs"
                      style={{ backgroundColor: item.color }}
                    />
                    <h5 className="font-bold text-sm text-slate-900">
                      {item.name}
                    </h5>
                  </div>
                  <span
                    className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border shadow-xs"
                    style={{
                      borderColor: item.color + '40',
                      backgroundColor: item.color + '15',
                      color: item.color,
                    }}
                  >
                    {item.id}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mb-3 leading-relaxed">
                  {item.description}
                </p>
              </div>

              <div className="pt-3 border-t border-[#f0e8dc] text-[11px] text-slate-500">
                <span className="font-semibold text-slate-700">Functional Risk: </span>
                {item.risk}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

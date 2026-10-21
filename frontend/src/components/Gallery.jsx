import React, { useState, useMemo } from 'react';
import {
  FileArchive,
  Download,
  Filter,
  Search,
  ArrowUpDown,
  AlertTriangle,
  Eye,
  CheckCircle2,
  Layers,
  FileSpreadsheet
} from 'lucide-react';
import { DEFECT_CLASSES } from '../config';

export default function Gallery({
  results,
  onImageClick,
  onDownloadZip,
  onDownloadCsv,
}) {
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'with_defects', 'without_defects'
  const [classFilter, setClassFilter] = useState('all');
  const [sortBy, setSortBy] = useState('defects_desc');
  const [searchQuery, setSearchQuery] = useState('');

  const images = results?.images || [];

  // Filter and sort computation
  const filteredImages = useMemo(() => {
    return images
      .filter((img) => {
        // Status filter
        if (statusFilter === 'with_defects' && (img.total_defects || 0) === 0) {
          return false;
        }
        if (statusFilter === 'without_defects' && (img.total_defects || 0) > 0) {
          return false;
        }

        // Class filter
        if (classFilter !== 'all') {
          const ds = img.defect_summary || {};
          if (!ds[classFilter] || ds[classFilter] <= 0) {
            return false;
          }
        }

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          if (!img.filename.toLowerCase().includes(q)) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'defects_desc') {
          return (b.total_defects || 0) - (a.total_defects || 0);
        }
        if (sortBy === 'defects_asc') {
          return (a.total_defects || 0) - (b.total_defects || 0);
        }
        if (sortBy === 'conf_desc') {
          const maxA = Math.max(...(a.detections?.map((d) => d.confidence) || [0]), 0);
          const maxB = Math.max(...(b.detections?.map((d) => d.confidence) || [0]), 0);
          return maxB - maxA;
        }
        if (sortBy === 'name_asc') {
          return a.filename.localeCompare(b.filename);
        }
        return 0;
      });
  }, [images, statusFilter, classFilter, sortBy, searchQuery]);

  return (
    <section id="results-gallery" className="space-y-6">
      {/* ===================== Summary Bar ===================== */}
      <div className="rounded-3xl p-6 sm:p-7 border bg-white border-[#e8dfd5] shadow-[0_4px_25px_-5px_rgba(217,119,6,0.06)] transition-all">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-4 border-b border-[#f0e7db]">
          <div>
            <h3 className="font-extrabold text-xl tracking-tight text-slate-900">
              Inspection Findings Gallery
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Inspected {results.total} circuit board images • Displaying {filteredImages.length} boards
            </p>
          </div>

          {/* Export Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={onDownloadCsv}
              className="py-2.5 px-4 rounded-xl text-xs font-bold border border-[#dfd4c4] bg-[#faf8f5] text-slate-800 hover:bg-amber-50 cursor-pointer shadow-xs flex items-center space-x-2 transition-all active:scale-95"
              title="Export batch defect summary as CSV report"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-700" />
              <span>Download Report (CSV)</span>
            </button>

            <button
              onClick={onDownloadZip}
              className="py-2.5 px-4 rounded-xl text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2 transition-all shadow-md cursor-pointer bg-gradient-to-r from-amber-600 via-amber-700 to-amber-800 hover:from-amber-700 hover:to-amber-900 shadow-amber-700/20 active:scale-95"
              title="Download consolidated ZIP with all full-size annotated JPEGs, report.csv, and report.json"
            >
              <FileArchive className="w-4 h-4" />
              <span>Download All (ZIP)</span>
            </button>
          </div>
        </div>

        {/* Aggregate Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 mb-5">
          <div className="p-3.5 rounded-xl border bg-[#faf8f5] border-[#e8dfd5] text-center">
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
              Total Boards
            </span>
            <div className="text-2xl font-mono font-extrabold text-slate-900 mt-0.5">
              {results.total}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border bg-red-500/10 border-red-500/20 text-center text-red-800">
            <span className="text-[11px] font-medium uppercase tracking-wider">
              With Detections
            </span>
            <div className="text-2xl font-mono font-extrabold mt-0.5">
              {results.images_with_detections}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border bg-emerald-500/10 border-emerald-500/20 text-center text-emerald-800">
            <span className="text-[11px] font-medium uppercase tracking-wider">
              No Detections
            </span>
            <div className="text-2xl font-mono font-extrabold mt-0.5">
              {results.images_without_detections}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border bg-amber-500/10 border-amber-500/20 text-center text-amber-800">
            <span className="text-[11px] font-medium uppercase tracking-wider">
              Total Defects
            </span>
            <div className="text-2xl font-mono font-extrabold mt-0.5">
              {results.total_defects}
            </div>
          </div>
        </div>

        {/* Per-Class Distribution Badges */}
        {results.per_class_counts && Object.keys(results.per_class_counts).length > 0 && (
          <div className="pt-3 border-t border-[#f0e7db] flex flex-wrap gap-2 items-center">
            <span className="text-xs font-semibold text-slate-500 mr-1">
              Class Breakdown:
            </span>
            {Object.entries(results.per_class_counts).map(([cls, count]) => {
              const meta = DEFECT_CLASSES[cls] || { color: '#94a3b8', name: cls };
              return (
                <span
                  key={cls}
                  className="px-2.5 py-1 rounded-lg text-xs font-mono font-semibold border flex items-center space-x-1.5 shadow-2xs"
                  style={{
                    backgroundColor: meta.color + '15',
                    borderColor: meta.color + '35',
                    color: meta.color,
                  }}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: meta.color }}
                  />
                  <span>{meta.name}:</span>
                  <strong className="font-extrabold">{count}</strong>
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* ===================== Honest Messaging Notice Banner ===================== */}
      <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-950 text-xs flex items-start space-x-3 shadow-xs">
        <AlertTriangle className="w-5 h-5 shrink-0 text-amber-700 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-bold block text-sm mb-0.5">
            Operational Quality Disclaimer:
          </span>
          No detections means nothing was found above the threshold, not a guarantee the board is defect-free.
          Best on high-resolution board photos; low-resolution images may be unreliable.
          All safety-critical assemblies must undergo full automated optical inspection and in-circuit electrical continuity validation.
        </div>
      </div>

      {/* ===================== Filters & Search Bar ===================== */}
      <div className="p-4 rounded-2xl border bg-white border-[#e8dfd5] shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Status Filters */}
        <div className="flex items-center space-x-1.5 bg-[#f6f1e8] p-1 rounded-xl">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-amber-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All ({results.total})
          </button>
          <button
            onClick={() => setStatusFilter('with_defects')}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer ${
              statusFilter === 'with_defects'
                ? 'bg-red-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-red-700'
            }`}
          >
            With Defects ({results.images_with_detections})
          </button>
          <button
            onClick={() => setStatusFilter('without_defects')}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer ${
              statusFilter === 'without_defects'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-emerald-700'
            }`}
          >
            No Detections ({results.images_without_detections})
          </button>
        </div>

        {/* Class Filter Dropdown */}
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="py-1.5 px-3 rounded-lg border border-[#dfd4c4] bg-[#faf8f5] text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-amber-500 cursor-pointer text-xs"
          >
            <option value="all">All Classes</option>
            {Object.values(DEFECT_CLASSES).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Sort Dropdown */}
        <div className="flex items-center space-x-2">
          <ArrowUpDown className="w-4 h-4 text-slate-400" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="py-1.5 px-3 rounded-lg border border-[#dfd4c4] bg-[#faf8f5] text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-amber-500 cursor-pointer text-xs"
          >
            <option value="defects_desc">Most Defects First</option>
            <option value="defects_asc">Least Defects First</option>
            <option value="conf_desc">Highest Confidence</option>
            <option value="name_asc">Filename (A-Z)</option>
          </select>
        </div>

        {/* Search input */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full py-1.5 pl-9 pr-3 rounded-lg border border-[#dfd4c4] bg-[#faf8f5] text-slate-800 placeholder:text-slate-400 text-xs focus:outline-hidden focus:ring-2 focus:ring-amber-500"
          />
        </div>
      </div>

      {/* ===================== Responsive Thumbnail Grid ===================== */}
      {filteredImages.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredImages.map((item) => {
            const hasDefects = (item.total_defects || 0) > 0;
            const maxConf = Math.max(
              ...(item.detections?.map((d) => d.confidence) || [0]),
              0
            );

            return (
              <div
                key={`${item.batch_id || 'b'}_${item.index}_${item.filename}`}
                onClick={() => onImageClick(item, filteredImages.indexOf(item))}
                className="group rounded-2xl border overflow-hidden bg-white border-[#e8dfd5] hover:border-amber-500 hover:shadow-lg transition-all cursor-pointer flex flex-col justify-between shadow-2xs"
              >
                {/* Fixed Aspect Ratio Thumbnail (No layout shift) */}
                <div className="relative aspect-4/3 bg-[#13241b] flex items-center justify-center overflow-hidden">
                  <img
                    src={item.thumb_url || item.image_url}
                    alt={item.filename}
                    loading="lazy"
                    className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
                  />

                  {/* Defect Status Pill Badge */}
                  <div
                    className={`absolute top-2.5 right-2.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold shadow-md border ${
                      hasDefects
                        ? 'bg-red-600 text-white border-red-400'
                        : 'bg-emerald-600 text-white border-emerald-400'
                    }`}
                  >
                    {hasDefects ? `${item.total_defects} Defects` : 'No Detections'}
                  </div>

                  {/* Hover Overlay Hint */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-semibold space-x-1.5 backdrop-blur-2xs">
                    <Eye className="w-4 h-4" />
                    <span>View Inspection Lightbox</span>
                  </div>
                </div>

                {/* Card Content & Metadata */}
                <div className="p-3.5 text-xs flex-1 flex flex-col justify-between">
                  <div>
                    {/* Filename & Dimensions */}
                    <div className="flex items-center justify-between mb-1">
                      <h4
                        className="font-mono font-bold truncate text-slate-800 max-w-[180px]"
                        title={item.filename}
                      >
                        {item.filename}
                      </h4>
                      <span className="text-[10px] font-mono text-slate-400 shrink-0">
                        {item.width}x{item.height}
                      </span>
                    </div>

                    {/* Defect Class Chips with Fixed Colors */}
                    {hasDefects && item.defect_summary && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {Object.entries(item.defect_summary).map(([cls, count]) => {
                          const meta = DEFECT_CLASSES[cls] || {
                            color: '#94a3b8',
                            name: cls,
                          };
                          return (
                            <span
                              key={cls}
                              className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold border flex items-center space-x-1"
                              style={{
                                backgroundColor: meta.color + '15',
                                borderColor: meta.color + '30',
                                color: meta.color,
                              }}
                            >
                              <span>{meta.name}</span>
                              <strong className="font-extrabold">({count})</strong>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Card Footer: Max Confidence & Warning */}
                  <div className="mt-3 pt-2.5 border-t border-[#f0e7db] flex items-center justify-between text-[11px]">
                    <span className="font-mono text-slate-500">
                      {hasDefects ? `Max Conf: ${(maxConf * 100).toFixed(0)}%` : 'No Defect Hits'}
                    </span>

                    {/* Warning chip if present (e.g. low resolution) */}
                    {item.warning ? (
                      <span
                        className="text-amber-700 flex items-center space-x-1 font-semibold truncate max-w-[120px]"
                        title={item.warning}
                      >
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                        <span className="truncate">Low Res</span>
                      </span>
                    ) : (
                      <span className="text-emerald-700 text-[10px] font-semibold">
                        Analyzed
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl border bg-white border-[#e8dfd5] text-slate-500">
          <Filter className="w-10 h-10 mx-auto mb-2 text-slate-300" />
          <p className="font-semibold text-sm text-slate-700">
            No boards match your filter criteria
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Try resetting the class or status filters.
          </p>
        </div>
      )}
    </section>
  );
}

// CircuitSight - Frontend Configuration & Constants

export const API_BASE_URL = '/api';

export const DEFAULT_CONF = 0.25;
export const DEFAULT_IOU = 0.45;
export const DEFAULT_IMGSZ = 1024;
export const DEFAULT_CLASSIFY_CROPS = false;

export const DEFECT_CLASSES = {
  missing_hole: {
    id: 'missing_hole',
    name: 'Missing Hole',
    color: '#f43f5e', // Rose
    border: 'border-rose-500/30',
    bg: 'bg-rose-500/15',
    text: 'text-rose-600 dark:text-rose-400',
    chip: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
    badge: 'bg-rose-500 text-white',
    description: 'A required through-hole via or component lead hole is absent on the PCB substrate.',
    risk: 'Component leads cannot be inserted; broken multi-layer electrical connectivity.',
    remediation: 'Check CNC drill breakage sensor and drill program. Scrap if plating is complete.',
  },
  mouse_bite: {
    id: 'mouse_bite',
    name: 'Mouse Bite',
    color: '#f97316', // Orange
    border: 'border-orange-500/30',
    bg: 'bg-orange-500/15',
    text: 'text-orange-600 dark:text-orange-400',
    chip: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
    badge: 'bg-orange-500 text-white',
    description: 'Ragged bite-like erosion along the edge of a copper trace or board breakaway tab.',
    risk: 'Reduces trace cross-sectional area, causing localized heating under heavy current.',
    remediation: 'Audit photoresist film adhesion and chemical etching rate uniformity.',
  },
  open_circuit: {
    id: 'open_circuit',
    name: 'Open Circuit',
    color: '#ef4444', // Red
    border: 'border-red-500/30',
    bg: 'bg-red-500/15',
    text: 'text-red-600 dark:text-red-400',
    chip: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
    badge: 'bg-red-500 text-white',
    description: 'Complete physical disconnection along a conductive copper trace line.',
    risk: 'Complete operational failure or power rail interruption in the circuit.',
    remediation: 'Micro-wire jumper rework for prototype; inspect photoresist adhesion in batch.',
  },
  short: {
    id: 'short',
    name: 'Short Circuit',
    color: '#a855f7', // Purple
    border: 'border-purple-500/30',
    bg: 'bg-purple-500/15',
    text: 'text-purple-600 dark:text-purple-400',
    chip: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
    badge: 'bg-purple-500 text-white',
    description: 'Unintended conductive copper bridge spanning between adjacent conductor traces.',
    risk: 'Catastrophic overcurrent, component burnout, and immediate power rail shutdown.',
    remediation: 'Laser ablation for prototype rework; examine photolithography mask cleanliness.',
  },
  spur: {
    id: 'spur',
    name: 'Spur Defect',
    color: '#f59e0b', // Amber
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/15',
    text: 'text-amber-600 dark:text-amber-400',
    chip: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    badge: 'bg-amber-500 text-white',
    description: 'Sharp unwanted copper protrusion projecting outwards from a conductor trace.',
    risk: 'Reduces dielectric spacing; increases risk of electrical arcing and signal noise.',
    remediation: 'Inspect exposure artwork clarity and rinse chemistry in chemical etching stage.',
  },
  spurious_copper: {
    id: 'spurious_copper',
    name: 'Spurious Copper',
    color: '#06b6d4', // Cyan
    border: 'border-cyan-500/30',
    bg: 'bg-cyan-500/15',
    text: 'text-cyan-600 dark:text-cyan-400',
    chip: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20',
    badge: 'bg-cyan-500 text-white',
    description: 'Isolated stray unetched copper island remaining on the dielectric substrate.',
    risk: 'Parasitic capacitive coupling and potential short-circuit under surface moisture.',
    remediation: 'Increase etching dwell duration or check acid regenerator oxidation levels.',
  },
};

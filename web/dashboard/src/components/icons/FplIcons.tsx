/**
 * FPL Analytics — Custom Icon System
 *
 * Brand: "Pulse" — FPL Pulse Analytics
 * Concept: A lightning-bolt / pulse motif representing real-time data insights
 *
 * Usage:
 *   import { PulseLogo, NavIcons, StatusIcons, MetricIcons } from "@/components/icons/FplIcons";
 *   <PulseLogo size={32} />
 *   <NavIcons.Briefing size={20} />
 *   <StatusIcons.Injured size={16} />
 */

import { type SVGProps } from "react";

/* ─── Types ────────────────────────────────────────────────── */
interface IconProps extends SVGProps<SVGSVGElement> {
  size?: number;
  className?: string;
}

const defaults = (size = 24): Pick<SVGProps<SVGSVGElement>, "width" | "height" | "fill" | "xmlns"> => ({
  width: size,
  height: size,
  fill: "none",
  xmlns: "http://www.w3.org/2000/svg",
});

/* ═══════════════════════════════════════════════════════════════
   BRAND MARKS
   ═══════════════════════════════════════════════════════════════ */

/** Main logo mark — stylised bolt/pulse hybrid */
export function PulseLogo({ size = 32, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" {...defaults(size)} className={className} {...props}>
      <defs>
        <linearGradient id="pulse-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a855f7" />
          <stop offset="50%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#6d28d9" />
        </linearGradient>
        <linearGradient id="pulse-glow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#c084fc" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Background circle */}
      <circle cx="16" cy="16" r="15" fill="url(#pulse-grad)" />
      <circle cx="16" cy="16" r="15" fill="url(#pulse-glow)" />
      {/* Bolt/pulse mark */}
      <path
        d="M18.5 4L10 17h5.5L13.5 28 22 15h-5.5L18.5 4z"
        fill="white"
        fillOpacity="0.95"
      />
      {/* Subtle pulse line through bolt */}
      <path
        d="M6 16h4l2-3 2 6 2-6 2 3h4"
        stroke="white"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeOpacity="0.3"
      />
    </svg>
  );
}

/** Wordmark — "FPL Pulse" text treatment (for header) */
export function PulseWordmark({ size = 120, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 140 28" width={size} height={size * (28 / 140)} fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <text x="0" y="21" fontFamily="Inter, system-ui, sans-serif" fontWeight="800" fontSize="20" fill="currentColor">
        <tspan fill="url(#wm-grad)">FPL</tspan>
        <tspan dx="4" fillOpacity="0.9"> Pulse</tspan>
      </text>
      <defs>
        <linearGradient id="wm-grad" x1="0" y1="0" x2="40" y2="20" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a855f7" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/** Favicon-optimised mark (works at 16×16) */
export function PulseFavicon({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <rect rx="4" width="16" height="16" fill="#7c3aed" />
      <path d="M9.5 2L5 8.5h3L6.5 14 11 7.5H8L9.5 2z" fill="white" />
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════
   NAVIGATION ICONS — one per page
   ═══════════════════════════════════════════════════════════════ */

/** Briefing — newspaper/sparkle hybrid */
function Briefing({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <line x1="7" y1="9" x2="17" y2="9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="7" y1="13" x2="13" y2="13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      {/* AI sparkle */}
      <path d="M17 14l.7 1.3 1.3.7-1.3.7-.7 1.3-.7-1.3-1.3-.7 1.3-.7z" fill="currentColor" opacity="0.7" />
    </svg>
  );
}

/** Players — person with stats bars */
function Players({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <circle cx="9" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      {/* Mini bar chart */}
      <rect x="17" y="13" width="2" height="7" rx="0.5" fill="currentColor" opacity="0.5" />
      <rect x="20" y="10" width="2" height="10" rx="0.5" fill="currentColor" opacity="0.7" />
    </svg>
  );
}

/** Fixtures — calendar grid */
function Fixtures({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <line x1="3" y1="9" x2="21" y2="9" stroke="currentColor" strokeWidth="1.8" />
      <line x1="8" y1="4" x2="8" y2="9" stroke="currentColor" strokeWidth="1.8" />
      <line x1="16" y1="4" x2="16" y2="9" stroke="currentColor" strokeWidth="1.8" />
      {/* Grid dots for fixture difficulty */}
      <circle cx="7" cy="13" r="1.2" fill="currentColor" opacity="0.4" />
      <circle cx="12" cy="13" r="1.2" fill="currentColor" opacity="0.7" />
      <circle cx="17" cy="13" r="1.2" fill="currentColor" />
      <circle cx="7" cy="17" r="1.2" fill="currentColor" opacity="0.7" />
      <circle cx="12" cy="17" r="1.2" fill="currentColor" opacity="0.4" />
      <circle cx="17" cy="17" r="1.2" fill="currentColor" opacity="0.7" />
    </svg>
  );
}

/** Transfers — swap arrows */
function Transfers({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <path d="M7 4v16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M4 7l3-3 3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M17 20V4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M14 17l3 3 3-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      {/* Price tag dot */}
      <circle cx="12" cy="12" r="1.5" fill="currentColor" opacity="0.4" />
    </svg>
  );
}

/** Teams — shield with strength indicator */
function Teams({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <path
        d="M12 3L4 7v5c0 5.25 3.4 9.8 8 11 4.6-1.2 8-5.75 8-11V7l-8-4z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      {/* Inner strength bars */}
      <rect x="9" y="10" width="6" height="1.5" rx="0.75" fill="currentColor" opacity="0.7" />
      <rect x="9" y="13" width="4.5" height="1.5" rx="0.75" fill="currentColor" opacity="0.5" />
      <rect x="9" y="16" width="3" height="1.5" rx="0.75" fill="currentColor" opacity="0.3" />
    </svg>
  );
}

/** Trends — line chart with pulse */
function Trends({ size = 20, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...defaults(size)} className={className} {...props}>
      <path
        d="M3 20l4-6 3 3 4-8 3 4 4-6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Pulse accent dot on peak */}
      <circle cx="17" cy="7" r="2" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.5" />
      <circle cx="17" cy="7" r="0.8" fill="currentColor" />
    </svg>
  );
}

export const NavIcons = {
  Briefing,
  Players,
  Fixtures,
  Transfers,
  Teams,
  Trends,
};

/* ═══════════════════════════════════════════════════════════════
   STATUS ICONS — player state indicators
   ═══════════════════════════════════════════════════════════════ */

/** Injured — bandaged cross */
function Injured({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <circle cx="8" cy="8" r="7" stroke="#ef4444" strokeWidth="1.5" fill="#ef4444" fillOpacity="0.1" />
      <path d="M5.5 8h5M8 5.5v5" stroke="#ef4444" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/** Doubtful — warning triangle */
function Doubtful({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path d="M8 2L1.5 13.5h13L8 2z" stroke="#f59e0b" strokeWidth="1.4" fill="#f59e0b" fillOpacity="0.1" strokeLinejoin="round" />
      <line x1="8" y1="6.5" x2="8" y2="10" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="11.8" r="0.7" fill="#f59e0b" />
    </svg>
  );
}

/** Available — check circle */
function Available({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <circle cx="8" cy="8" r="7" stroke="#22c55e" strokeWidth="1.5" fill="#22c55e" fillOpacity="0.1" />
      <path d="M5.5 8l2 2 3-4" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Suspended — red card */
function Suspended({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <rect x="4" y="2" width="8" height="12" rx="1.5" fill="#ef4444" fillOpacity="0.85" stroke="#ef4444" strokeWidth="1" />
      <text x="8" y="10.5" textAnchor="middle" fill="white" fontSize="7" fontWeight="700" fontFamily="Inter, sans-serif">!</text>
    </svg>
  );
}

/** New signing — sparkle/star */
function NewSigning({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path
        d="M8 1l1.8 3.6L14 5.3l-3 2.9.7 4.1L8 10.4l-3.7 1.9.7-4.1-3-2.9 4.2-.7z"
        stroke="#a855f7"
        strokeWidth="1.2"
        fill="#a855f7"
        fillOpacity="0.15"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const StatusIcons = {
  Injured,
  Doubtful,
  Available,
  Suspended,
  NewSigning,
};

/* ═══════════════════════════════════════════════════════════════
   METRIC ICONS — data point indicators for dashboard cards
   ═══════════════════════════════════════════════════════════════ */

/** Price rising */
function PriceUp({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path d="M4 12l4-8 4 8" stroke="#22c55e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="#22c55e" fillOpacity="0.15" />
    </svg>
  );
}

/** Price falling */
function PriceDown({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path d="M4 4l4 8 4-8" stroke="#ef4444" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="#ef4444" fillOpacity="0.15" />
    </svg>
  );
}

/** Form — flame icon */
function Form({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path
        d="M8 1.5C6 4 4.5 6 4.5 8.5a3.5 3.5 0 007 0c0-1.2-.5-2.2-1.2-3.2-.3.8-.8 1.5-1.5 1.5-.5 0-1-.5-.8-1.5.3-1.5 0-2.5 0-3.8z"
        stroke="#f59e0b"
        strokeWidth="1.2"
        fill="#f59e0b"
        fillOpacity="0.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** xG / Expected goals — target */
function ExpectedGoals({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      <circle cx="8" cy="8" r="4" stroke="currentColor" strokeWidth="1.2" opacity="0.5" />
      <circle cx="8" cy="8" r="1.5" fill="currentColor" opacity="0.7" />
    </svg>
  );
}

/** Ownership — crowd/people */
function Ownership({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <circle cx="6" cy="5" r="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M2 13c0-2.2 1.8-4 4-4s4 1.8 4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="11" cy="5.5" r="1.5" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <path d="M11 9c1.7 0 3 1.3 3 3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}

/** ICT Index — radar pulse */
function IctIndex({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8 8l4-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
      <path d="M3.5 3.5a6.5 6.5 0 019 0" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.3" />
      <path d="M5 5a4.2 4.2 0 016 0" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}

/** Momentum — wave */
function Momentum({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path
        d="M1 8c1.5-3 3-3 4.5 0S8.5 11 10 8s3-3 4.5 0"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

/** Value — diamond/gem */
function Value({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path d="M4 6h8l-4 8z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" fill="currentColor" fillOpacity="0.1" />
      <path d="M4 6l2-3h4l2 3" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      <path d="M6 3l2 3 2-3" stroke="currentColor" strokeWidth="1" opacity="0.4" strokeLinejoin="round" />
    </svg>
  );
}

/** AI Insight — brain/sparkle */
function AiInsight({ size = 16, className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...defaults(size)} className={className} {...props}>
      <path d="M8 2l1 2 2 1-2 1-1 2-1-2-2-1 2-1z" fill="#a855f7" opacity="0.8" />
      <path d="M11.5 8l.7 1.3 1.3.7-1.3.7-.7 1.3-.7-1.3-1.3-.7 1.3-.7z" fill="#a855f7" opacity="0.5" />
      <path d="M5 10l.5 1 1 .5-1 .5-.5 1-.5-1-1-.5 1-.5z" fill="#a855f7" opacity="0.3" />
    </svg>
  );
}

export const MetricIcons = {
  PriceUp,
  PriceDown,
  Form,
  ExpectedGoals,
  Ownership,
  IctIndex,
  Momentum,
  Value,
  AiInsight,
};

/* ═══════════════════════════════════════════════════════════════
   POSITION BADGES — GKP / DEF / MID / FWD
   ═══════════════════════════════════════════════════════════════ */

interface PositionBadgeProps extends IconProps {
  position: "GKP" | "DEF" | "MID" | "FWD";
}

const positionColors: Record<string, { bg: string; text: string }> = {
  GKP: { bg: "#eab308", text: "#1a1a1a" },
  DEF: { bg: "#7c3aed", text: "#ffffff" },
  MID: { bg: "#22c55e", text: "#1a1a1a" },
  FWD: { bg: "#ef4444", text: "#ffffff" },
};

export function PositionBadge({ position, size = 28, className, ...props }: PositionBadgeProps) {
  const c = positionColors[position] ?? positionColors.MID;
  return (
    <svg viewBox="0 0 32 18" width={size} height={size * (18 / 32)} className={className} {...props}>
      <rect width="32" height="18" rx="4" fill={c.bg} />
      <text x="16" y="13" textAnchor="middle" fill={c.text} fontSize="10" fontWeight="700" fontFamily="Inter, system-ui, sans-serif">
        {position}
      </text>
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════
   FDR DIFFICULTY DOT — tiny fixture difficulty indicator
   ═══════════════════════════════════════════════════════════════ */

interface FdrDotProps extends IconProps {
  level: 1 | 2 | 3 | 4 | 5;
}

const fdrColors = ["#22c55e", "#4ade80", "#94a3b8", "#f87171", "#dc2626"];

export function FdrDot({ level, size = 12, className, ...props }: FdrDotProps) {
  return (
    <svg viewBox="0 0 12 12" {...defaults(size)} className={className} {...props}>
      <circle cx="6" cy="6" r="5" fill={fdrColors[level - 1]} />
      <text x="6" y="9" textAnchor="middle" fill="white" fontSize="7" fontWeight="600" fontFamily="Inter, sans-serif">
        {level}
      </text>
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════
   RECOMMENDATION BADGES — Buy / Sell / Hold / Watch
   ═══════════════════════════════════════════════════════════════ */

interface RecBadgeProps extends IconProps {
  rec: "buy" | "sell" | "hold" | "watch";
}

const recConfig: Record<string, { color: string; symbol: string }> = {
  buy:   { color: "#22c55e", symbol: "+" },
  sell:  { color: "#ef4444", symbol: "−" },
  hold:  { color: "#94a3b8", symbol: "=" },
  watch: { color: "#f59e0b", symbol: "?" },
};

export function RecBadge({ rec, size = 20, className, ...props }: RecBadgeProps) {
  const c = recConfig[rec];
  return (
    <svg viewBox="0 0 20 20" {...defaults(size)} className={className} {...props}>
      <circle cx="10" cy="10" r="9" fill={c.color} fillOpacity="0.15" stroke={c.color} strokeWidth="1.5" />
      <text x="10" y="14" textAnchor="middle" fill={c.color} fontSize="12" fontWeight="700" fontFamily="Inter, sans-serif">
        {c.symbol}
      </text>
    </svg>
  );
}

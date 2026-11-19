import React from 'react'

export const glyphs = {
  wood: <><path d="m12 2 5 7h-3l6 8H4l6-8H7Z" fill="currentColor" strokeLinejoin="round"/><path d="M12 17v4"/></>,
  brick: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 12h18m-10-7v7m4 0v7"/></>,
  wool: <><path d="M7 17a4 4 0 0 1-2-7 4 4 0 0 1 6-4 4 4 0 0 1 7 3 4 4 0 0 1-1 8Zm2 0v4m7-4v4"/><path d="M18 10l3-2 1 4-3 3"/></>,
  grain: <><path d="m6 21 12-17m-3 6c-4 0-6-2-6-6 4 0 7 2 6 6Zm-4 5c-4 0-6-2-6-6 4 0 7 2 6 6Zm2-2c4 1 7-1 8-4-4-1-7 0-8 4Zm-4 5c4 1 7-1 8-4-4-1-7 0-8 4Z"/></>,
  ore: <><path d="m2 18 5-9 5 9Zm7 0 6-13 7 13Z"/><path d="m12 11 3 1 3-1"/></>,
  desert: <><circle cx="13" cy="8" r="3"/><path d="M2 18q6-8 12 0 4-4 8 0M2 21h20"/></>,
  road: <><path d="m5 20 7-16h6l-2 16Z"/><path d="m12 18 3-11" strokeDasharray="2 3"/></>,
  home: <><path d="m3 11 9-7 9 7M5 10v10h14V10M10 20v-5h4v5"/></>,
  city: <><path d="M2 20V9h4V5h4v6l6-4 6 4v9ZM7 14v2m8-3v2m3-2v2"/></>,
  buy: <><rect x="5" y="2" width="14" height="20" rx="2"/><path d="m12 6 1.8 4 4.2 1-3 3 .5 4-3.5-2-3.5 2 .5-4-3-3 4.2-1Z"/></>,
  trade: <><path d="M3 8h17m-4-4 4 4-4 4m5 4H4m4-4-4 4 4 4"/></>,
  end: <><path d="M3 12h14m-5-5 5 5-5 5m8-12v14"/></>,
  dice: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 8h.01M16 8h.01M12 12h.01M8 16h.01M16 16h.01" strokeWidth="2.8"/></>,
  flag: <><path d="M5 21V3q4-2 8 0t7 0v10q-3 2-7 0t-8 0"/></>,
}

export function Icon({kind, className}) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{glyphs[kind]}</svg>
}

export function Landmarks({resource, x, y}) {
  return <g className="isle-landmarks" transform={`translate(${x},${y-9})`} aria-hidden="true">
    <path className="isle-land-etch" d="M-36-7l12 3m-15 13 9 2m4-28 8 2M20-16l12 4M24 8l11-3M16 14l9-1"/>
    <svg x="-13" y="-18" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round">{glyphs[resource]}</svg>
  </g>
}

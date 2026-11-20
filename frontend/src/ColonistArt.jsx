import React from 'react'

export const glyphs = {
  wood: <><path d="m12 2 5 7h-3l6 8H4l6-8H7Z" fill="currentColor" strokeLinejoin="round"/><path d="M12 17v4"/></>,
  brick: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 12h18m-10-7v7m4 0v7"/></>,
  wool: <><path d="M7 17a4 4 0 0 1-2-7 4 4 0 0 1 6-4 4 4 0 0 1 7 3 4 4 0 0 1-1 8Zm2 0v4m7-4v4"/><path d="M18 10l3-2 1 4-3 3"/></>,
  grain: <><path d="m6 21 12-17m-3 6c-4 0-6-2-6-6 4 0 7 2 6 6Zm-4 5c-4 0-6-2-6-6 4 0 7 2 6 6Zm2-2c4 1 7-1 8-4-4-1-7 0-8 4Zm-4 5c4 1 7-1 8-4-4-1-7 0-8 4Z"/></>,
  ore: <><path d="m2 18 5-9 5 9Zm7 0 6-13 7 13Z"/><path d="m12 11 3 1 3-1"/></>,
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

// Each orientation places its face at the front before the cube is tilted.
const DIE_FACES = [
  {turn:'rotateY(0deg)', front:'rotateY(0deg)', pips:[5]},
  {turn:'rotateY(90deg)', front:'rotateY(-90deg)', pips:[1,9]},
  {turn:'rotateX(90deg)', front:'rotateX(-90deg)', pips:[1,5,9]},
  {turn:'rotateX(-90deg)', front:'rotateX(90deg)', pips:[1,3,7,9]},
  {turn:'rotateY(-90deg)', front:'rotateY(90deg)', pips:[1,3,5,7,9]},
  {turn:'rotateY(180deg)', front:'rotateY(-180deg)', pips:[1,3,4,6,7,9]},
]

export function Dice({values, animate}) {
  return <div className={`isle-dice${animate ? ' is-rolling' : ''}`} role="img" aria-label={`Кубики: ${values.join(' и ')}`}>
    {values.map((value, index) => <div className="isle-die" key={index} style={{'--face-up':DIE_FACES[value-1].front}}>
      <div className="isle-die-cube">
        {DIE_FACES.map(({turn, pips}, face) => <div key={turn} className="isle-die-face" data-main={face+1 === value}
          style={{'--face-turn':turn}}>
          {pips.map(pip => <i key={pip} style={{gridArea:`${Math.ceil(pip/3)} / ${(pip-1)%3+1}`}}/>)}
        </div>)}
      </div>
    </div>)}
  </div>
}

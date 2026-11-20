import React, {useEffect, useId, useRef} from 'react'
import {createPortal} from 'react-dom'

export function CaseDialog({title,children,onClose,wide=false}) {
 const ref=useRef(null)
 const titleId=useId()
 useEffect(()=>{const dialog=ref.current;dialog.showModal();return()=>{if(dialog.open)dialog.close()}},[])
 return createPortal(<dialog ref={ref} className={`case-dialog ${wide?'case-dialog-wide':''}`} aria-labelledby={titleId}
  onCancel={event => {event.preventDefault();onClose?.()}}
  onClick={event => {if(event.target===event.currentTarget)onClose?.()}}>
  <div className="cd-heading"><h2 id={titleId}>{title}</h2>
   {onClose && <button type="button" className="dc-icon-button" onClick={onClose} aria-label="Закрыть">×</button>}
  </div>
  <div className="cd-content">{children}</div>
 </dialog>,document.body)
}
export function CaseEmpty({icon='◎',title,children,action}) {
 return <div className="dc-empty"><span>{icon}</span><h3>{title}</h3><p>{children}</p>{action}</div>
}
export function EvidenceImage({item,className=''}) {
 return item.image?<img className={className} src={item.image} alt={item.caption||item.title} style={item.portrait_position?{objectPosition:item.portrait_position}:undefined}/>:<span className="dc-evidence-symbol">{item.icon}</span>
}

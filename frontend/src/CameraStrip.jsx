import React, {createContext, useContext, useState} from 'react'

export const CameraContext = createContext(null)

export default function CameraStrip() {
  const {video, enabled, setEnabled} = useContext(CameraContext)
  const [confirming, setConfirming] = useState(false)
  if (!video) return null

  const params = new URLSearchParams({room: video.room, password: video.password, label: video.name, showlabels: '', webcam: '', autostart: ''})
  const src = `https://vdo.ninja/#${params.toString()}`

  return <section className="cameras" aria-label="Камеры игроков">
    <div className="cameras-header">
      <div><span className="eyebrow">ВИДИМ ДРУГ ДРУГА</span><h2>Камеры игроков</h2></div>
      {enabled ? <button type="button" className="outline-button cameras-toggle" onClick={() => setEnabled(false)}>Выключить камеру</button> : <button type="button" className="outline-button cameras-toggle" onClick={() => setConfirming(true)}>Включить камеру</button>}
    </div>
    {confirming && !enabled && <div className="camera-confirm" role="group" aria-label="Подтверждение включения камеры">
      <p>Камера и микрофон будут доступны другим участникам лобби через VDO.Ninja. Браузер попросит разрешение на доступ.</p>
      <div className="camera-confirm-actions"><button type="button" className="button" onClick={() => {setEnabled(true); setConfirming(false)}}>Разрешить и включить</button><button type="button" className="outline-button" onClick={() => setConfirming(false)}>Отмена</button></div>
    </div>}
    {enabled ? <div className="camera-video"><iframe title="Камеры игроков через VDO.Ninja" src={src} allow="camera; microphone; autoplay; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="no-referrer"/></div> : !confirming && <p className="cameras-empty">Включи камеру, чтобы видеть и слышать друзей во время игры.</p>}
  </section>
}

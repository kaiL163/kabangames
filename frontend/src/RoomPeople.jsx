import React, {createContext, useContext, useMemo} from 'react'
import {AccountLink, Avatar} from './Account.jsx'

const RoomPeople = createContext(null)

export function RoomPeopleProvider({data, children}) {
  const people = useMemo(() => {
    const directory = new Map()
    if (data?.host_name) directory.set(data.host_name, data.host_avatar)
    for (const player of data?.players ?? []) directory.set(player.name, player.avatar)
    return directory
  }, [data?.host_name, data?.host_avatar, data?.players])
  return <RoomPeople.Provider value={people}>{children}</RoomPeople.Provider>
}

export function PlayerName({name, suffix}) {
  const avatar = useContext(RoomPeople)?.get(name)
  const initial = name?.trim().slice(0, 1).toUpperCase() || '•'
  return <span className="player-identity">
    <span className="player-identity-icon" aria-hidden="true"><Avatar id={avatar} fallback={initial}/></span>
    <span className="player-identity-name">{name}{suffix}</span>
  </span>
}

export function RoundHeader({room, onBack, onRules}) {
  return <div className="game-bar">
    <span>КОМНАТА {room.code}</span>
    <div className="game-bar-actions">
      <AccountLink game/>
      <button className="outline-button" onClick={onRules}>Как играть</button>
      <button className="outline-button" onClick={onBack}>{room.host ? 'Завершить игру' : 'В лобби'}</button>
    </div>
  </div>
}

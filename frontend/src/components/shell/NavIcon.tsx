export function NavIcon({name}:{name:string}) {
 const paths:Record<string,string>={"/":"M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z","/watchlists":"M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01","/alerts":"M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4","/backtests":"M3 3v18h18M6 16l5-6 4 3 6-8","/strategies":"M4 7h16M4 17h16M8 4v6M16 14v6","/admin":"M3 4h18v16H3zM8 4v16M12 9h5M12 14h5"};
 return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]??paths['/']}/></svg>;
}

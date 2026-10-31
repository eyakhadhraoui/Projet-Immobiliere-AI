/** Bloc d'erreur avec, le cas échéant, les messages par champ et un bouton Réessayer. */
export default function MessageErreur({ erreur, onReessayer }) {
  const champs = Object.entries(erreur.champs ?? {})

  return (
    <div className="etat etat--erreur" role="alert">
      <p>{erreur.message}</p>
      {champs.length > 0 && (
        <ul>
          {champs.map(([champ, messages]) => (
            <li key={champ}>
              <strong>{champ}</strong> : {messages.join(' ')}
            </li>
          ))}
        </ul>
      )}
      {onReessayer && (
        <button type="button" className="bouton bouton--principal" onClick={onReessayer}>
          Réessayer
        </button>
      )}
    </div>
  )
}

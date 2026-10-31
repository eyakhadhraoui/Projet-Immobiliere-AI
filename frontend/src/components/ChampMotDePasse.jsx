import { useState } from 'react'

/**
 * Champ mot de passe avec bouton « Afficher / Masquer ».
 * aria : attributs fournis par <Champ> (id, name, aria-invalid, aria-describedby).
 */
export default function ChampMotDePasse({ aria, value, onChange, autoComplete }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="mot-de-passe">
      <input {...aria} type={visible ? 'text' : 'password'} value={value} onChange={onChange} autoComplete={autoComplete} />
      <button
        type="button"
        className="mot-de-passe__bascule"
        onClick={() => setVisible((v) => !v)}
        aria-controls={aria.id}
        aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
      >
        {visible ? 'Masquer' : 'Afficher'}
      </button>
    </div>
  )
}

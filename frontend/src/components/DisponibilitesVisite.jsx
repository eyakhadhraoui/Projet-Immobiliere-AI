const JOURS = [
  [1, 'Lundi'], [2, 'Mardi'], [3, 'Mercredi'], [4, 'Jeudi'],
  [5, 'Vendredi'], [6, 'Samedi'], [7, 'Dimanche'],
]

export default function DisponibilitesVisite({ valeur = [], onChange }) {
  const parJour = new Map(valeur.map((item) => [Number(item.jour_semaine), item]))

  function modifier(jour, actif, champ, contenu) {
    const prochain = valeur.filter((item) => Number(item.jour_semaine) !== jour)
    const precedent = parJour.get(jour) || { jour_semaine: jour, heure_debut: '09:00', heure_fin: '17:00' }
    if (actif) prochain.push({ ...precedent, [champ]: contenu })
    onChange(prochain.sort((a, b) => a.jour_semaine - b.jour_semaine))
  }

  return (
    <fieldset className="formulaire__groupe disponibilites-visite">
      <legend>Disponibilités pour les visites</legend>
      <p className="formulaire__aide">
        Cochez les jours et indiquez les horaires pendant lesquels les visiteurs peuvent demander un créneau.
      </p>
      <div className="disponibilites-visite__liste">
        {JOURS.map(([jour, libelle]) => {
          const item = parJour.get(jour)
          return (
            <div className="disponibilite-visite" key={jour}>
              <label className="champ--case">
                <input
                  type="checkbox"
                  checked={Boolean(item)}
                  onChange={(event) => modifier(jour, event.target.checked, 'heure_debut', item?.heure_debut || '09:00')}
                />
                <span>{libelle}</span>
              </label>
              <label>
                <span className="visuellement-cache">Début {libelle}</span>
                <input
                  type="time"
                  value={item?.heure_debut || '09:00'}
                  disabled={!item}
                  onChange={(event) => modifier(jour, true, 'heure_debut', event.target.value)}
                />
              </label>
              <span aria-hidden="true">à</span>
              <label>
                <span className="visuellement-cache">Fin {libelle}</span>
                <input
                  type="time"
                  value={item?.heure_fin || '17:00'}
                  disabled={!item}
                  onChange={(event) => modifier(jour, true, 'heure_fin', event.target.value)}
                />
              </label>
            </div>
          )
        })}
      </div>
    </fieldset>
  )
}

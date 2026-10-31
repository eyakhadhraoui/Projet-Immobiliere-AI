/**
 * Badge public « Bonne affaire » / « Prix dans le marché » / « Prix au-dessus du marché ».
 *
 * Calculé par l'API (IA-ANNONCE-001-ROBUSTE) en comparant le prix à la FOURCHETTE estimée ; l'API n'en renvoie pas
 * (marche = null) si le modèle est absent ou si la confiance est faible : rien n'est alors affiché.
 * L'infobulle (survol ou focus clavier) et le texte réservé aux lecteurs d'écran rappellent qu'il s'agit d'une
 * estimation indicative, pas d'une expertise.
 */
export default function BadgeMarche({ marche }) {
  if (!marche) return null
  return (
    <p className="marche">
      <span
        className={`badge badge-marche badge-marche--${marche.position}`}
        data-infobulle="Estimation indicative"
        tabIndex={0}
      >
        {marche.libelle}
        <span className="visuellement-cache"> (estimation indicative)</span>
      </span>
    </p>
  )
}

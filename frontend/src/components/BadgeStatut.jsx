import { LIBELLES_STATUT } from '../utils/format'

/** Pastille colorée indiquant le statut d'une annonce. */
export default function BadgeStatut({ statut }) {
  return <span className={`badge badge--${statut}`}>{LIBELLES_STATUT[statut] ?? statut}</span>
}

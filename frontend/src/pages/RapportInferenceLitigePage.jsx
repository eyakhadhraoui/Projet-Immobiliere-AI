import { Link } from 'react-router-dom'
import './RapportInferenceLitigePage.css'

const JOURNAL = [
  '[01:16:45 UTC] Résultat 1/4 : RÉUSSI | étayé | génération locale | 72,10 s',
  '[01:17:31 UTC] Résultat 2/4 : ÉCHEC | citations ou valeur invalides | génération locale | 45,46 s',
  '[01:18:19 UTC] Résultat 3/4 : ÉCHEC | citations ou valeur invalides | génération locale | 48,63 s',
  '[01:18:20 UTC] Résultat 4/4 : RÉUSSI | preuves insuffisantes | abstention du reclasseur | 0,28 s',
  '[01:18:20 UTC] Fin des 4 questions illustratives. Serveur du modèle fermé. Rapports de précision existants inchangés.',
]

function CarteInference({ id, titre, statut, methode, duree, question, reponse, valeur, etatModele, citations = [] }) {
  const reussite = statut === 'Réussi'
  return (
    <article className={`rapport-inference__scenario ${reussite ? 'est-reussi' : 'est-rejete'}`} id={id}>
      <header>
        <h3>{titre}</h3>
        <p className="rapport-inference__statut"><strong>CONTRÔLE {reussite ? 'RÉUSSI' : 'ÉCHOUÉ'}</strong> · {duree} · {methode}</p>
        <p className="rapport-inference__question">{question}</p>
      </header>
      <div className="rapport-inference__scenario-corps">
        <section>
          <h4>Réponse du modèle / pipeline</h4>
          <p>{reponse}</p>
          <span className="rapport-inference__libelle">Valeur structurée</span>
          <strong className="rapport-inference__valeur">{valeur || 'Aucune valeur'}</strong>
          <small>État du modèle : {etatModele}</small>
        </section>
        <section>
          <h4>Sources et citations</h4>
          {citations.length ? citations.map((citation) => (
            <blockquote key={citation.titre}>
              <strong>{citation.titre}</strong>
              <span className="rapport-inference__auteur">Auteur indiqué : {citation.auteur}</span>
              <span className="rapport-inference__validation">{citation.validation}</span>
              <p>{citation.texte}</p>
              {citation.original && <><span className="rapport-inference__libelle">Texte réel de la source</span><p>{citation.original}</p></>}
            </blockquote>
          )) : <><p>Aucune citation renvoyée.</p><small>L’absence de citation ici ne prouve pas qu’aucune autre pièce ne contient l’information.</small></>}
        </section>
      </div>
      <section className="rapport-inference__controle">
        <h4>Contrôle indépendant</h4>
        <p>{reussite ? 'Le contrôle confirme le comportement attendu pour ce cas fictif.' : 'Le brouillon a été rejeté au contrôle des citations ou des valeurs; il n’est pas présenté comme une réponse validée.'}</p>
      </section>
    </article>
  )
}

export default function RapportInferenceLitigePage() {
  return (
    <main className="rapport-inference" aria-labelledby="titre-rapport-inference">
      <header className="rapport-inference__intro">
        <p className="rapport-inference__sur-titre">ORGANISATEUR DE PREUVES DE LITIGE LOCATIF</p>
        <p className="rapport-inference__sur-titre rapport-inference__sur-titre--doux">TRADUCTION DES RÉSULTATS ENREGISTRÉS DANS LES CAPTURES</p>
        <h1 id="titre-rapport-inference">Résultats enregistrés du modèle local</h1>
        <p>Quatre questions fixes sur un cas fictif. Les réponses acceptées et les brouillons rejetés sont conservés.</p>
      </header>

      <aside className="rapport-inference__resume" role="note">
        <strong>2 / 4 contrôles illustratifs réussis</strong>
        <p>Cette démonstration ne constitue pas une nouvelle mesure de précision.</p>
        <p>Ces résultats proviennent des captures fournies; ils ne sont pas produits par le modèle actuellement installé dans l’application.</p>
      </aside>

      <nav className="rapport-inference__sommaire" aria-label="Questions de la démonstration">
        <a href="#loyer">Loyer mensuel</a><a href="#retenue">Retenue proposée</a><a href="#parties">Versions des parties</a><a href="#remboursement">Preuve de remboursement</a><a href="#recherche">Recherche des preuves</a>
      </nav>

      <section className="rapport-inference__grille" aria-label="Résultat de chaque question">
        <CarteInference id="loyer" titre="Loyer mensuel" statut="Réussi" methode="génération locale" duree="72,10 s"
          question="Quel loyer mensuel est convenu dans le contrat de location signé ?"
          reponse="Le contrat de location signé indique un loyer mensuel de 700 EUR."
          valeur="700 EUR" etatModele="étayé"
          citations={[{ titre: 'D2-p1 · Extrait du bail', auteur: 'les deux parties', validation: 'CITATION EXACTE', texte: 'Le contrat de location signé indique un dépôt de garantie de 1 000 EUR et un loyer mensuel de 700 EUR.' }]} />

        <CarteInference id="retenue" titre="Retenue proposée" statut="Échoué" methode="génération locale" duree="45,46 s"
          question="Quelle retenue le bailleur affirme-t-il vouloir effectuer sur le dépôt de garantie ?"
          reponse="Le bailleur affirme qu’il veut retenir 200 EUR du dépôt de garantie pour une rayure sur le sol de la chambre."
          valeur="200 EUR" etatModele="étayé par le modèle, mais brouillon rejeté par le programme"
          citations={[{ titre: 'D4-p1 · Message du bailleur', auteur: 'bailleur', validation: 'CITATION NON CONFORME — BROUILLON REJETÉ', texte: 'Le bailleur déclare : « Je compte déduire 200 EUR du dépôt de garantie pour la rayure sur le sol de la chambre. »', original: '2026-03-03 : Le bailleur déclare : « Je compte déduire 200 EUR du dépôt de garantie pour la rayure sur le sol de la chambre. Je pense que ce dommage est survenu pendant votre location. » Aucune facture de réparation n’est jointe à ce message.' }]} />

        <CarteInference id="parties" titre="Versions des parties" statut="Échoué" methode="génération locale" duree="48,63 s"
          question="Le bailleur et le locataire sont-ils d’accord sur la présence de la rayure au sol de la chambre lors de l’entrée dans le logement ?"
          reponse="Le locataire indique que la rayure était déjà présente à son arrivée; le bailleur affirme que le dommage s’est produit pendant la location."
          valeur="Aucune valeur" etatModele="versions contradictoires"
          citations={[
            { titre: 'D5-p1 · Réponse du locataire', auteur: 'locataire', validation: 'CITATION NON CONFORME — BROUILLON REJETÉ', texte: 'Le locataire indique : « Je conteste la retenue de 200 EUR. La rayure au sol de la chambre était déjà présente à mon arrivée. »', original: '2026-03-04 : Le locataire indique : « Je conteste la retenue de 200 EUR. La rayure au sol de la chambre était déjà présente à mon arrivée. Veuillez comparer l’état des lieux d’entrée signé et m’envoyer une explication détaillée. » Il s’agit de la version du locataire.' },
            { titre: 'D4-p1 · Message de retenue du bailleur', auteur: 'bailleur', validation: 'CITATION NON CONFORME — BROUILLON REJETÉ', texte: 'Le bailleur indique : « Je pense que ce dommage est survenu pendant votre location. »', original: '2026-03-03 : Le bailleur déclare vouloir déduire 200 EUR du dépôt de garantie pour une rayure sur le sol de la chambre. Il estime que le dommage est survenu pendant la location. Aucune facture de réparation n’est jointe.' },
          ]} />

        <CarteInference id="remboursement" titre="Preuve de remboursement" statut="Réussi" methode="abstention du reclasseur" duree="0,28 s"
          question="Quel montant du dépôt de garantie a été remboursé au locataire ?"
          reponse="Les passages retrouvés ne fournissent pas de preuve suffisamment pertinente pour répondre à cette question."
          valeur="Aucune valeur" etatModele="preuves insuffisantes"
          citations={[]} />
      </section>

      <section className="rapport-inference__bloc" id="precision" aria-labelledby="titre-precision">
        <h2 id="titre-precision">Résultats de précision enregistrés précédemment</h2>
        <p>Développement : <strong>56/60 corrects (93,3 %)</strong>.</p>
        <p>Test de contrôle incomplet : <strong>12/16 corrects (75 %)</strong>.</p>
        <p>Seules 16 des 80 questions prévues ont été traitées.</p>
        <small>Tous les cas sont synthétiques. L’objectif de 80 % sur le test final et la précision sur des cas réels restent non vérifiés.</small>
      </section>

      <section className="rapport-inference__bloc rapport-inference__recherche" id="recherche" aria-labelledby="titre-recherche">
        <h2 id="titre-recherche">Du questionnement aux pièces justificatives</h2>
        <p className="rapport-inference__question">Question enregistrée : « Quelle retenue le bailleur affirme-t-il vouloir effectuer sur le dépôt de garantie ? »</p>
        <p className="rapport-inference__etapes">7 documents sources · recherche par mots-clés et sémantique · reclasseur MiniLM entraîné · 5 passages sélectionnés</p>
        <p>Les scores affichés dans la capture sont des logits bruts du réseau, pas des probabilités calibrées. La fusion hybride détermine l’ordre final.</p>
        <div className="rapport-inference__passages">
          <article><strong>RANG 1 · D4 · LOGIT 5,325</strong><h3>Message de retenue du bailleur</h3><p>Auteur indiqué : bailleur</p><blockquote>2026-03-03 : Le bailleur déclare vouloir déduire 200 EUR du dépôt de garantie pour la rayure sur le sol de la chambre…</blockquote></article>
          <article><strong>RANG 2 · D6 · LOGIT -1,970</strong><h3>Courriel de remise des clés</h3><p>Auteur indiqué : bailleur</p><blockquote>2026-02-28 : Le bailleur confirme la réception des clés aujourd’hui. Merci d’avoir organisé la remise…</blockquote></article>
          <article><strong>RANG 3 · D2 · LOGIT -3,461</strong><h3>Extrait du bail</h3><p>Auteur indiqué : les deux parties</p><blockquote>Le contrat signé indique un dépôt de garantie de 1 000 EUR et un loyer mensuel de 700 EUR. La durée ferme se termine le 28/02/2026…</blockquote></article>
          <article><strong>RANG 4 · D5 · LOGIT -6,238</strong><h3>Réponse du locataire</h3><p>Auteur indiqué : locataire</p><blockquote>2026-03-04 : Le locataire conteste la retenue de 200 EUR et indique que la rayure était déjà présente à son arrivée…</blockquote></article>
          <article><strong>RANG 5 · D3 · LOGIT -7,569</strong><h3>Reçu de paiement du dépôt</h3><p>Auteur indiqué : prestataire de paiement</p><blockquote>2025-09-02 : Le reçu REF-DEP-001 consigne un virement de 1 000 EUR du locataire au bailleur. Le motif indique « dépôt de garantie »…</blockquote></article>
        </div>
      </section>

      <section className="rapport-inference__bloc" aria-labelledby="titre-journal">
        <h2 id="titre-journal">Journal d’exécution enregistré</h2>
        <pre>{JOURNAL.join('\n')}</pre>
        <p>Préfixe SHA-256 du point de contrôle entraîné : <code>3061fbbf580fdb4504b16274</code>.</p>
      </section>

      <footer className="rapport-inference__pied">
        <p>Cas fictif · Sorties de modèle enregistrées · Contrôles illustratifs, pas une mesure de précision générale.</p>
        <p>Exécution : 2026-10-26 01:15:28 UTC · Traduction des six captures fournies.</p>
        <Link to="/dossiers-litige">Retour aux dossiers de litige</Link>
      </footer>
    </main>
  )
}

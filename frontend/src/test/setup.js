import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// findBy… / waitFor attendent 1 s par défaut : trop court quand la machine est chargée
// (FRONT-004 : un test passait seul mais échouait dans la suite complète, sans erreur de code).
configure({ asyncUtilTimeout: 5000 })

// jsdom n'implémente pas les URL d'objets (aperçus des photos choisies).
if (!URL.createObjectURL) {
  let compteur = 0
  URL.createObjectURL = () => `blob:apercu-${++compteur}`
  URL.revokeObjectURL = () => {}
}

// Démonte les composants rendus entre deux tests (Vitest sans "globals").
afterEach(() => {
  cleanup()
})

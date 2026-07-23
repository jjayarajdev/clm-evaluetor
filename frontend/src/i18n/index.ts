import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import fr from './locales/fr.json'

export type AppLanguage = 'en' | 'fr'

export function getStoredLanguage(): AppLanguage {
  const stored = localStorage.getItem('language')
  return stored === 'fr' ? 'fr' : 'en'
}

export function setAppLanguage(language: AppLanguage) {
  localStorage.setItem('language', language)
  i18n.changeLanguage(language)
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fr: { translation: fr },
  },
  lng: getStoredLanguage(),
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
})

export default i18n

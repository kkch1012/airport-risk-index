import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import ko from './locales/ko.json';
import en from './locales/en.json';

const savedLang = localStorage.getItem('i18n-lang') || 'ko';

i18n.use(initReactI18next).init({
  resources: {
    ko: { translation: ko },
    en: { translation: en },
  },
  lng: savedLang,
  fallbackLng: 'ko',
  interpolation: {
    escapeValue: false,
  },
});

i18n.on('languageChanged', (lng) => {
  localStorage.setItem('i18n-lang', lng);
  document.documentElement.lang = lng;
});

// 초기 lang 속성 설정
document.documentElement.lang = savedLang;

export default i18n;

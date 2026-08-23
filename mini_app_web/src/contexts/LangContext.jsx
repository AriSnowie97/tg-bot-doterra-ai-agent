import { createContext, useState, useContext, useEffect } from "react";
import ua from "../locales/ua.json";
import en from "../locales/en.json";

const LangContext = createContext();

export const useLang = () => useContext(LangContext);

export const LangProvider = ({ children }) => {
    const [lang, setLang] = useState(() => {
        return localStorage.getItem("app_lang") || "ua";
    });

    useEffect(() => {
        localStorage.setItem("app_lang", lang);
    }, [lang]);

    const toggleLang = () => {
        setLang(prev => (prev === "ua" ? "en" : "ua"));
    };

    const dict = lang === "en" ? en : ua;

    const t = (key) => {
        return dict[key] || key;
    };

    return (
        <LangContext.Provider value={{ lang, toggleLang, t }}>
            {children}
        </LangContext.Provider>
    );
};

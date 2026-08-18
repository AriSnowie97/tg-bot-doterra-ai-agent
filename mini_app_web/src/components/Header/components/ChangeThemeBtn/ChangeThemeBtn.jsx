import { useState, useEffect } from "react";

import styles from "./ChangeThemeBtn.module.css";

const SunIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" className={styles.icon}>
        <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2"/>
        <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
);

const MoonIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" className={styles.icon}>
        <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 109.79 9.79z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
);

const ChangeThemeBtn = () => {
    const [theme, setTheme] = useState("light");

    useEffect(() => {
        document.documentElement.setAttribute("color-theme", theme);
    }, [theme]);

    const changeTheme = () => {
        theme === "light" ? setTheme("dark") : setTheme("light");
    };

    return (
        <div className={styles.wrapper} onClick={changeTheme} title={theme === "light" ? "Темна тема" : "Світла тема"}>
            {theme === "light" ? <SunIcon /> : <MoonIcon />}
        </div>
    );
};

export {ChangeThemeBtn};
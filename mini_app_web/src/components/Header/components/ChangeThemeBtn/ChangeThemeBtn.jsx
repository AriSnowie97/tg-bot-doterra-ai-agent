import { useState, useEffect } from "react";

import styles from "./ChangeThemeBtn.module.css";
import { SunSvg } from "../../../../assets/icons";
import { MoonSvg } from "../../../../assets/icons";


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
            {theme === "light" ? <SunSvg className={styles.icon} /> : <MoonSvg className={styles.icon} />}
        </div>
    );
};

export {ChangeThemeBtn};
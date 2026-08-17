import { useState, useEffect } from "react";

import styles from "./ChangeThemeBtn.module.css";

const ChangeThemeBtn = () => {
    const [theme, setTheme] = useState("light");

    useEffect(() => {
        document.documentElement.setAttribute("color-theme", theme);
    }, [theme]);

    const changeTheme= () => {
        theme=="light"
        ? setTheme("dark")
        : setTheme("light")
    }

    return (
        <>
            <div className={styles.wrapper} onClick={changeTheme}>
                <img src={
                    theme=="light"
                    ? "light.png"
                    : "dark.png"
                } alt="theme"/>
            </div>
        </>
    );
}

export {ChangeThemeBtn};
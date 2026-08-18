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
                {
                    theme=="light"
                    ? <p>☀️</p>
                    :<p>🌙</p>
                }
            </div>
        </>
    );
}

export {ChangeThemeBtn};
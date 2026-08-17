import { Link } from "react-router-dom";

import styles from "./Header.module.css";
import heroImg from "/src/assets/hero.png";
import { ChangeThemeBtn } from "./components/ChangeThemeBtn";
import { ChangeLangBtn } from "./components/ChangeLangBtn";


const Header = () => {
    return (
        <>
            <header>
                <div className={styles.btnWrapper}>
                    <ChangeThemeBtn />
                    <ChangeLangBtn />
                </div>
            </header>
        </>
    );
}

export {Header};
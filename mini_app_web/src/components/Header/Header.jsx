import { Link, useLocation } from "react-router-dom";

import styles from "./Header.module.css";
import heroImg from "/src/assets/hero.png";
import { ChangeThemeBtn } from "./components/ChangeThemeBtn";
import { ChangeLangBtn } from "./components/ChangeLangBtn";


const Header = () => {
    const location = useLocation();
    const isChat = location.pathname === '/chat';

    return (
        <>
            <header>
                {isChat ? (
                    <div className={styles.headerInfo}>
                        <span className={styles.headerTitle}>ШІ Асистент doTERRA</span>
                        <span className={styles.headerSubtitle} id="typing-indicator" style={{ display: 'none' }}>друкує...</span>
                    </div>
                ) : (
                    <div />
                )}
                <div className={styles.btnWrapper}>
                    <ChangeThemeBtn />
                    <ChangeLangBtn />
                </div>
            </header>
        </>
    );
}

export {Header};
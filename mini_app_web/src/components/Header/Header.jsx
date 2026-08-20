import { Link, useLocation } from "react-router-dom";

import styles from "./Header.module.css";
import heroImg from "/src/assets/hero.png";
import { ChangeThemeBtn } from "./components/ChangeThemeBtn";
import { ChangeLangBtn } from "./components/ChangeLangBtn";
import { useLang } from "../../contexts/LangContext";


const Header = () => {
    const location = useLocation();
    const isChat = location.pathname === '/chat';
    const { t } = useLang();

    return (
        <>
            <header>
                {isChat ? (
                    <div className={styles.headerInfo}>
                        <span className={styles.headerTitle}>{t("header_title")}</span>
                        <span className={styles.headerSubtitle} id="typing-indicator" style={{ display: 'none' }}>{t("chat_typing")}</span>
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
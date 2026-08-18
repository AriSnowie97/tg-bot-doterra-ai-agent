import styles from "./ChangeLangBtn.module.css";

const GlobeIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" className={styles.icon}>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
        <path d="M12 3c-2 3-3 5.5-3 9s1 6 3 9M12 3c2 3 3 5.5 3 9s-1 6-3 9M3 12h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
);

const ChangeLangBtn = () => {
    return (
        <div className={styles.wrapper} title="Мова">
            <GlobeIcon />
        </div>
    );
}

export {ChangeLangBtn};
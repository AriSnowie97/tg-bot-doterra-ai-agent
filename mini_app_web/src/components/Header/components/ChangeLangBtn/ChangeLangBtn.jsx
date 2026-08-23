import styles from "./ChangeLangBtn.module.css";
import { useLang } from "../../../../contexts/LangContext";
import { GlobeSvg } from "../../../../assets/icons";


const ChangeLangBtn = () => {
    const { lang, toggleLang } = useLang();

    return (
        <div className={styles.wrapper} title="Language" onClick={toggleLang}>
            <GlobeSvg className={styles.icon} />
            <span style={{fontSize: "14px", fontWeight: "bold", textTransform: "uppercase"}}>{lang}</span>
        </div>
    );
}

export {ChangeLangBtn};

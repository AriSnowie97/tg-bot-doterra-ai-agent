import { Link } from "react-router-dom";

import styles from "./LinkBtn.module.css";
import { useLang } from "../../../../../contexts/LangContext";


const LinkBtn = ({linkTo, Svg, subject, newStyles}) => {
    const { t } = useLang();
    
    return (
        <>
            <Link to={linkTo} className={`${styles.linkToBtn} ${newStyles.linkToBtn || ""}`}>
                <div className={`${styles.wrapper} ${newStyles.wrapper || ""}`}>
                    <div className={`${styles.img} ${newStyles.img || ""}`}>
                        <Svg className={styles.Svg} />
                    </div>
                    <div className={`${styles.text} ${newStyles.text || ""}`}>
                        <h3>{t("link_btns")?.[subject]?.title ?? "title"}</h3>
                        <p>{t("link_btns")?.[subject]?.description ?? "description"}</p>
                    </div>
                    <div className={`${styles.arrow} ${newStyles.arrow || ""}`}>
                        <p>→</p>
                    </div>
                </div>
            </Link>
        </>
    );
}

export {LinkBtn};
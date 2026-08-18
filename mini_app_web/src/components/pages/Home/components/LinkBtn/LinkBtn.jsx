import { Link } from "react-router-dom";

import styles from "./LinkBtn.module.css";


const LinkBtn = ({linkTo, Svg, h3Text, pText, newStyles}) => {
    
    return (
        <>
            <Link to={linkTo} className={`${styles.linkToBtn} ${newStyles.linkToBtn || ""}`}>
                <div className={`${styles.wrapper} ${newStyles.wrapper || ""}`}>
                    <div className={`${styles.img} ${newStyles.img || ""}`}>
                        <Svg className={styles.Svg} />
                    </div>
                    <div className={`${styles.text} ${newStyles.text || ""}`}>
                        <h3>{h3Text}</h3>
                        <p>{pText}</p>
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
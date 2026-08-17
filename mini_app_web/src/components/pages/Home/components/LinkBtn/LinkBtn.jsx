import { Link } from "react-router-dom";

import styles from "./LinkBtn.module.css";


const LinkBtn = ({linkTo, img, h3Text, pText, newStyles}) => {
    
    return (
        <>
            <Link to={linkTo} className={styles.linkToBtn}>
                <div className={`${styles.wrapper} ${newStyles.wrapper || ""}`}>
                    <div className={`${styles.img} ${newStyles.img || ""}`}>
                        <img src={img || "link.png"} alt="link"/>
                    </div>
                    <div className={`${styles.text} ${newStyles.text || ""}`}>
                        <h3>{h3Text}</h3>
                        <p>{pText}</p>
                    </div>
                    <div className={`${styles.arrow} ${newStyles.arrow || ""}`}>
                        <p><code>{"-->"}</code></p>
                    </div>
                </div>
            </Link>
        </>
    );
}

export {LinkBtn};
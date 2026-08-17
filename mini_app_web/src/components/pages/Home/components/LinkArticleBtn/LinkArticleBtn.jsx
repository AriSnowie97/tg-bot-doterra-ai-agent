import { Link } from "react-router-dom";

import styles from "./LinkArticleBtn.module.css";

const LinkArticleBtn = () => {
    return (
        <>
            <Link to="/" className={styles.linkToBtn}>
                <div className={styles.wrapper}>
                    <img src="art.png" alt="article"/>
                    <h3>Text</h3>
                </div>
            </Link>
        </>
    );
}

export {LinkArticleBtn};
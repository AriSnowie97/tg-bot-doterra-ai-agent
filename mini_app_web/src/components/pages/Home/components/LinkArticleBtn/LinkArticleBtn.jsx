import { Link } from "react-router-dom";

import styles from "./LinkArticleBtn.module.css";

const LinkArticleBtn = ({data}) => {
    return (
        <>
            <Link to="/articles" className={styles.linkToBtn}>
                <div className={styles.wrapper}>
                    <div className={styles.img}>Prod Img</div>
                    <h3>{data.title}</h3>
                </div>
            </Link>
        </>
    );
}

export {LinkArticleBtn};
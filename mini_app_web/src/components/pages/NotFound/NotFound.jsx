import { useLocation } from "react-router-dom";

import styles from "./NotFound.module.css";
import { useLang } from "../../../contexts/LangContext";


const NotFound = () => {
    const location = useLocation();
    const { t } = useLang();


    return (
        <>
            <div className={styles.wrapper}>
                <p>404 {t("nothing_found")} D;</p>
                <p style={{fontSize: "10px", marginTop: "10px", color: "red"}}>Path: {location.pathname}{location.search}{location.hash}</p>
            </div>
        </>
    );
}

export {NotFound};